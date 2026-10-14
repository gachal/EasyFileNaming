"""主窗口:选择文件夹 → 识别(后台线程)→ 预览表 → 应用/撤销/设置/自诊断。"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections import OrderedDict

import wx
import wx.grid

from ..core import rename_plan as rp
from ..core import scanner, settings as settings_mod, undo as undo_mod
from ..core.applier import Applier
from ..core.diagnostics import report_text, run_diagnostic, write_report
from ..core.ocr import OcrEngine, OcrError
from ..core.title_extractor import extract_title, sanitize_name

COL_THUMB, COL_STATUS, COL_OLD, COL_NEW, COL_CONF, COL_METHOD = range(6)
COL_LABELS = ("预览", "状态", "旧文件名", "新文件名(可改)", "置信度", "方式")

CLR_UNRECOGNIZED = wx.Colour(255, 249, 219)
CLR_FAILED = wx.Colour(253, 227, 227)
CLR_DONE = wx.Colour(228, 244, 229)


class ThumbRenderer(wx.grid.GridCellRenderer):
    """缩略图渲染:LRU 缓存,缺失时画占位框。"""

    _cache = OrderedDict()  # type: OrderedDict
    _CAP = 400
    _SIZE = (56, 44)

    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        path = grid.GetCellValue(row, col)
        bmp = self._lookup(path)
        if bmp is None:
            dc.SetBrush(wx.Brush(wx.Colour(240, 240, 240)))
            dc.SetPen(wx.Pen(wx.Colour(205, 205, 205)))
            dc.DrawRectangle(
                rect.x + 6, rect.y + 4, rect.width - 12, rect.height - 8
            )
            return
        w, h = bmp.GetSize()
        x = rect.x + (rect.width - w) // 2
        y = rect.y + (rect.height - h) // 2
        dc.DrawBitmap(bmp, x, y, True)

    def GetBestSize(self, grid, attr, dc, row, col):
        return wx.Size(*self._SIZE)

    def Clone(self):
        return ThumbRenderer()

    @classmethod
    def _lookup(cls, path):
        if not path:
            return None
        if path in cls._cache:
            cls._cache.move_to_end(path)
            return cls._cache[path]
        bmp = cls._load(path)
        cls._cache[path] = bmp
        while len(cls._cache) > cls._CAP:
            cls._cache.popitem(last=False)
        return bmp

    @classmethod
    def _load(cls, path):
        try:
            img = wx.Image(path, wx.BITMAP_TYPE_ANY)
            if not img.IsOk():
                return None
            bw, bh = cls._SIZE
            ratio = min(bw / img.GetWidth(), bh / img.GetHeight())
            w = max(1, int(img.GetWidth() * ratio))
            h = max(1, int(img.GetHeight() * ratio))
            img.Rescale(w, h, wx.IMAGE_QUALITY_LOW)
            return wx.Bitmap(img)
        except Exception:
            return None


class MainFrame(wx.Frame):
    def __init__(self, parent, title):
        wx.Frame.__init__(
            self, parent, title=title,
            size=(1180, 720),
        )
        self.settings = settings_mod.load()
        self.folder = ""
        self.entries = []
        self._cancel = None
        self._worker = None

        self._build_ui()
        self._bind_events()
        self._set_busy(False)
        self._update_summary()
        self._maybe_first_run_diagnostic()

    # ---------- 界面搭建 ----------

    def _build_ui(self):
        top = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        row1 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_pick = wx.Button(top, label="选择文件夹")
        self.lbl_folder = wx.StaticText(top, label="(未选择)")
        self.lbl_folder.SetFont(wx.Font(wx.FontInfo(10).Bold()))
        self.cb_recursive = wx.CheckBox(top, label="含子文件夹")
        self.cb_recursive.SetValue(self.settings.recursive)
        row1.Add(self.btn_pick, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row1.Add(self.lbl_folder, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row1.Add(self.cb_recursive, 0, wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(row1, 0, wx.ALL | wx.EXPAND, 8)

        row2 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_recognize = wx.Button(top, label="开始识别")
        self.btn_cancel = wx.Button(top, label="取消")
        self.gauge = wx.Gauge(top)
        self.lbl_progress = wx.StaticText(top, label="就绪")
        row2.Add(self.btn_recognize, 0, wx.RIGHT, 8)
        row2.Add(self.btn_cancel, 0, wx.RIGHT, 8)
        row2.Add(self.gauge, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row2.Add(self.lbl_progress, 1, wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(row2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        self.grid = wx.grid.Grid(top)
        self.grid.CreateGrid(0, len(COL_LABELS))
        for i, label in enumerate(COL_LABELS):
            self.grid.SetColLabelValue(i, label)
        widths = (64, 76, 300, 240, 64, 64)
        for i, w in enumerate(widths):
            self.grid.SetColSize(i, w)
        self.grid.SetDefaultRowSize(48, resizeExistingRows=True)
        self.grid.SetRowLabelSize(44)
        self.grid.EnableDragRowSize(False)
        vbox.Add(self.grid, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 8)

        row3 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_apply = wx.Button(top, label="应用改名")
        self.btn_apply.SetFont(wx.Font(wx.FontInfo(10).Bold()))
        self.btn_undo = wx.Button(top, label="撤销…")
        self.btn_settings = wx.Button(top, label="设置…")
        self.btn_diag = wx.Button(top, label="自诊断")
        self.lbl_summary = wx.StaticText(top, label="")
        row3.Add(self.btn_apply, 0, wx.RIGHT, 8)
        row3.Add(self.btn_undo, 0, wx.RIGHT, 8)
        row3.Add(self.btn_settings, 0, wx.RIGHT, 8)
        row3.Add(self.btn_diag, 0, wx.RIGHT, 8)
        row3.Add(self.lbl_summary, 1, wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(row3, 0, wx.ALL | wx.EXPAND, 8)

        top.SetSizer(vbox)

    def _bind_events(self):
        self.btn_pick.Bind(wx.EVT_BUTTON, self._on_pick)
        self.btn_recognize.Bind(wx.EVT_BUTTON, self._on_recognize)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self._on_cancel)
        self.btn_apply.Bind(wx.EVT_BUTTON, self._on_apply)
        self.btn_undo.Bind(wx.EVT_BUTTON, self._on_undo)
        self.btn_settings.Bind(wx.EVT_BUTTON, self._on_settings)
        self.btn_diag.Bind(wx.EVT_BUTTON, self._on_diagnostic)
        self.cb_recursive.Bind(wx.EVT_CHECKBOX, self._on_recursive_toggled)
        self.grid.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self._on_cell_changed)
        self.grid.Bind(
            wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self._on_cell_dclicked
        )
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ---------- 状态控制 ----------

    def _set_busy(self, busy):
        self.btn_recognize.Enable(not busy)
        self.btn_pick.Enable(not busy)
        self.btn_apply.Enable(not busy)
        self.btn_cancel.Enable(busy)
        if not busy:
            self.gauge.SetValue(0)

    def _update_summary(self):
        if not self.entries:
            self.lbl_summary.SetLabel("共 0 张")
            return
        counts = {}
        for e in self.entries:
            counts[e.status] = counts.get(e.status, 0) + 1
        parts = ["{} {}".format(v, k) for k, v in counts.items()]
        self.lbl_summary.SetLabel(
            "共 {} 张:".format(len(self.entries)) + "、".join(parts)
        )

    # ---------- 选择文件夹 / 识别 ----------

    def _on_pick(self, event):
        dlg = wx.DirDialog(self, "选择要处理的文件夹",
                           style=wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        self.folder = dlg.GetPath()
        dlg.Destroy()
        self.lbl_folder.SetLabel(self.folder)
        self.entries = []
        self._reset_grid()
        self._update_summary()
        self.lbl_progress.SetLabel("就绪,点「开始识别」")

    def _on_recursive_toggled(self, event):
        self.settings.recursive = self.cb_recursive.GetValue()
        settings_mod.save(self.settings)

    def _on_recognize(self, event):
        if not self.folder or not os.path.isdir(self.folder):
            wx.MessageBox("请先选择文件夹", "提示", wx.ICON_INFORMATION)
            return
        paths = scanner.scan_folder(
            self.folder, self.cb_recursive.GetValue()
        )
        if not paths:
            wx.MessageBox(
                "该文件夹里没有可处理的图片(jpg/jpeg/png/bmp/webp)",
                "提示", wx.ICON_INFORMATION,
            )
            return
        self.entries = []
        self._reset_grid()
        self._cancel = threading.Event()
        self._set_busy(True)
        self._worker = threading.Thread(
            target=self._recognize_worker, args=(paths,), daemon=True
        )
        self._worker.start()

    def _recognize_worker(self, paths):
        titles = {}
        notes = {}
        try:
            engine = OcrEngine()
        except OcrError as exc:
            wx.CallAfter(self._on_recognition_failed_engine, str(exc))
            return
        total = len(paths)
        for i, path in enumerate(paths):
            if self._cancel.is_set():
                wx.CallAfter(
                    self._on_recognition_done, paths, titles, notes, True
                )
                return
            try:
                lines = engine.recognize(path)
                title = extract_title(
                    lines,
                    self.settings.min_confidence,
                    self.settings.max_title_len,
                )
            except OcrError as exc:
                title = None
                notes[path] = str(exc)
            titles[path] = title
            wx.CallAfter(self._on_one_done, i, total, path)
        wx.CallAfter(self._on_recognition_done, paths, titles, notes, False)

    def _on_one_done(self, i, total, path):
        self.gauge.SetValue(int((i + 1) * 100 / max(total, 1)))
        self.lbl_progress.SetLabel(
            "{}/{} — {}".format(i + 1, total, os.path.basename(path))
        )

    def _on_recognition_failed_engine(self, error):
        self._set_busy(False)
        self.lbl_progress.SetLabel("识别引擎加载失败")
        wx.MessageBox(
            "识别引擎加载失败,无法自动识别。\n{}\n\n"
            "仍可手动在「新文件名」列输入名称后应用改名;"
            "建议先运行「自诊断」并导出日志反馈。".format(error),
            "识别引擎失败", wx.ICON_ERROR,
        )

    def _on_recognition_done(self, paths, titles, notes, cancelled):
        self._set_busy(False)
        self.lbl_progress.SetLabel("已取消" if cancelled else "识别完成")
        plan = rp.build_plan(self.folder, paths, titles, self.settings)
        self.entries = plan.entries
        for e in self.entries:
            if e.path in notes:
                e.note = notes[e.path]
                e.status = rp.ST_FAILED
        self._fill_grid()
        self._update_summary()

    def _on_cancel(self, event):
        if self._cancel:
            self._cancel.set()

    # ---------- 预览表 ----------

    def _reset_grid(self):
        n = self.grid.GetNumberRows()
        if n:
            self.grid.DeleteRows(0, n)
        ThumbRenderer._cache.clear()

    def _fill_grid(self):
        self._reset_grid()
        n = len(self.entries)
        if not n:
            return
        self.grid.AppendRows(n)
        for i, e in enumerate(self.entries):
            self.grid.SetCellValue(i, COL_THUMB, e.path)
            self.grid.SetCellRenderer(i, COL_THUMB, ThumbRenderer())
            self.grid.SetCellValue(i, COL_STATUS, e.status)
            self.grid.SetCellValue(i, COL_OLD, os.path.basename(e.path))
            self.grid.SetCellValue(i, COL_NEW, e.final if e.final else "")
            self.grid.SetCellValue(
                i, COL_CONF,
                "{:.2f}".format(e.confidence) if e.confidence else "",
            )
            self.grid.SetCellValue(i, COL_METHOD, e.method)
            for col in (COL_THUMB, COL_STATUS, COL_OLD, COL_CONF,
                        COL_METHOD):
                self.grid.SetReadOnly(i, col, True)
            if e.status == rp.ST_UNRECOGNIZED:
                self.grid.SetCellBackgroundColour(
                    i, COL_STATUS, CLR_UNRECOGNIZED
                )
            elif e.status == rp.ST_FAILED:
                self.grid.SetCellBackgroundColour(i, COL_STATUS, CLR_FAILED)
            elif e.status == rp.ST_DONE:
                self.grid.SetCellBackgroundColour(i, COL_STATUS, CLR_DONE)

    def _on_cell_changed(self, event):
        row, col = event.GetRow(), event.GetCol()
        if col != COL_NEW or row >= len(self.entries):
            return
        value = sanitize_name(self.grid.GetCellValue(row, col))
        self.grid.SetCellValue(row, col, value)
        e = self.entries[row]
        if not value:
            e.final = None
            if e.status != rp.ST_DONE:
                e.status = rp.ST_UNRECOGNIZED
        else:
            e.final = value
            if e.status != rp.ST_DONE:
                e.status = rp.ST_OK
        self.grid.SetCellValue(row, COL_STATUS, e.status)
        self._update_summary()

    def _on_cell_dclicked(self, event):
        if event.GetCol() == COL_NEW:
            event.Skip()  # 新名列双击进入编辑
            return
        row = event.GetRow()
        if 0 <= row < len(self.entries):
            self._open_file(self.entries[row].path)

    @staticmethod
    def _open_file(path):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif os.name == "nt":
                os.startfile(path)  # Windows only
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError:
            pass

    # ---------- 应用 / 撤销 ----------

    def _on_apply(self, event):
        actions = [e for e in self.entries if e.final and e.final != e.stem]
        if not actions:
            wx.MessageBox(
                "没有待改名的行:识别出的行可先在「新文件名」列确认或修改,"
                "未识别的行可手动输入名称。",
                "提示", wx.ICON_INFORMATION,
            )
            return
        if wx.MessageBox(
            "将重命名 {} 个文件,可在「撤销…」中恢复。\n确认应用?".format(
                len(actions)
            ),
            "确认改名", wx.YES_NO | wx.ICON_QUESTION,
        ) != wx.YES:
            return
        wx.BeginBusyCursor()
        try:
            result = Applier().apply(actions)
        finally:
            wx.EndBusyCursor()
        if result.renamed:
            undo_mod.save_undo_log(result.renamed, self.folder)
            renamed_paths = {r["old"] for r in result.renamed}
            for e in self.entries:
                if e.path in renamed_paths:
                    e.status = rp.ST_DONE
                    e.path = os.path.join(
                        os.path.dirname(e.path), e.final + e.ext
                    )
        for f in result.failed:
            for e in self.entries:
                if e.path == f.path:
                    e.status = rp.ST_FAILED
                    e.note = "{}: {}".format(f.stage, f.error)
        self._fill_grid()
        self._update_summary()
        self.lbl_progress.SetLabel(
            "改名完成:成功 {} / 失败 {}".format(
                len(result.renamed), len(result.failed)
            )
        )
        if result.failed:
            lines = [
                "{}\n  {}".format(f.path, f.error) for f in result.failed[:20]
            ]
            wx.MessageBox(
                "{} 个文件改名失败:\n\n{}".format(
                    len(result.failed), "\n".join(lines)
                ),
                "部分失败", wx.ICON_WARNING,
            )

    def _on_undo(self, event):
        logs = undo_mod.list_undo_logs()
        if not logs:
            wx.MessageBox("没有可撤销的改名记录。", "撤销", wx.ICON_INFORMATION)
            return
        choices = [
            "{} | {} | {} 项".format(
                lg.time, os.path.basename(lg.folder) or lg.folder, lg.count
            )
            for lg in logs
        ]
        dlg = wx.SingleChoiceDialog(
            self, "选择要恢复的记录(按当时时间):", "撤销改名", choices
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        idx = dlg.GetSelection()
        dlg.Destroy()
        restored, skipped, notes = undo_mod.restore_log(logs[idx].path)
        msg = "恢复 {} 个,跳过 {} 个。".format(restored, skipped)
        if notes:
            msg += "\n\n" + "\n".join(notes[:15])
        wx.MessageBox(msg, "撤销完成", wx.ICON_INFORMATION)
        if restored:
            self.entries = []
            self._reset_grid()
            self._update_summary()
            self.lbl_progress.SetLabel("已恢复,可重新识别验证")

    # ---------- 设置 / 自诊断 ----------

    def _on_settings(self, event):
        dlg = wx.Dialog(self, title="设置")
        vbox = wx.BoxSizer(wx.VERTICAL)
        cb_recursive = wx.CheckBox(dlg, label="识别时包含子文件夹")
        cb_recursive.SetValue(self.settings.recursive)
        cb_date = wx.CheckBox(dlg, label="名称后追加文件修改日期(YYYYMMDD)")
        cb_date.SetValue(self.settings.append_date)
        st_conf = wx.StaticText(
            dlg, label="OCR 置信度阈值(低于此值不参与命名):"
        )
        sp_conf = wx.SpinCtrlDouble(
            dlg, min=0.3, max=0.95, initial=self.settings.min_confidence,
            inc=0.05,
        )
        st_len = wx.StaticText(dlg, label="文件名最大字符数:")
        sp_len = wx.SpinCtrl(
            dlg, min=10, max=100, initial=self.settings.max_title_len
        )
        for w in (cb_recursive, cb_date, st_conf, sp_conf, st_len, sp_len):
            vbox.Add(w, 0, wx.ALL, 6)
        btns = dlg.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        vbox.Add(btns, 0, wx.EXPAND | wx.ALL, 6)
        dlg.SetSizerAndFit(vbox)
        if dlg.ShowModal() == wx.ID_OK:
            self.settings.recursive = cb_recursive.GetValue()
            self.settings.append_date = cb_date.GetValue()
            self.settings.min_confidence = round(sp_conf.GetValue(), 2)
            self.settings.max_title_len = sp_len.GetValue()
            settings_mod.save(self.settings)
            self.cb_recursive.SetValue(self.settings.recursive)
            if self.entries:
                self.lbl_progress.SetLabel(
                    "设置已保存;标题规则下次识别时生效"
                )
        dlg.Destroy()

    def _on_diagnostic(self, event):
        self.btn_diag.Enable(False)
        self.lbl_progress.SetLabel("自诊断运行中…")

        def work():
            report = run_diagnostic()
            wx.CallAfter(self._show_diagnostic, report)

        threading.Thread(target=work, daemon=True).start()

    def _show_diagnostic(self, report):
        self.btn_diag.Enable(True)
        self.lbl_progress.SetLabel(
            "自诊断:{}".format("通过" if report.ok else "失败")
        )
        dlg = wx.Dialog(
            self, title="自诊断 " + ("(通过)" if report.ok else "(失败)")
        )
        vbox = wx.BoxSizer(wx.VERTICAL)
        txt = wx.TextCtrl(
            dlg, value=report_text(report),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
            size=(640, 420),
        )
        vbox.Add(txt, 1, wx.ALL | wx.EXPAND, 8)
        btns = wx.BoxSizer(wx.HORIZONTAL)
        btn_export = wx.Button(dlg, label="导出报告…")
        btn_close = wx.Button(dlg, label="关闭")
        btns.Add(btn_export, 0, wx.RIGHT, 8)
        btns.Add(btn_close)
        vbox.Add(btns, 0, wx.ALIGN_RIGHT | wx.ALL, 8)
        dlg.SetSizerAndFit(vbox)
        btn_close.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_OK))
        btn_export.Bind(
            wx.EVT_BUTTON, lambda e: self._export_report(report)
        )
        dlg.ShowModal()
        dlg.Destroy()

    def _export_report(self, report):
        path = write_report(report)
        wx.MessageBox(
            "报告已导出:\n{}\n请把该文件发回给提供者以排查问题。".format(path),
            "导出完成", wx.ICON_INFORMATION,
        )

    def _maybe_first_run_diagnostic(self):
        if self.settings.diagnostic_ok is not None:
            return

        def work():
            report = run_diagnostic()
            self.settings.diagnostic_ok = report.ok
            settings_mod.save(self.settings)
            if not report.ok:
                wx.CallAfter(self._show_diagnostic, report)

        threading.Thread(target=work, daemon=True).start()

    def _on_close(self, event):
        if self._cancel:
            self._cancel.set()
        event.Skip()
