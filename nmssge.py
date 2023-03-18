#!/usr/bin/env python

import collections.abc
import io
import json
import sys
from pathlib import Path

import lz4.block
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

data = [0]

"""Savegame (de)compressor and (de|en)coder."""

decode_mapping: dict[str, str] = json.loads(Path(__file__).resolve().with_suffix('.json').read_text())
encode_mapping: dict[str, str] = {v: k for k, v in decode_mapping.items()}


def decode(src: str, strict: bool = False) -> dict:
	"""Decode from json."""

	def decoder(src: list[tuple[any, any]]) -> dict:
		"""Json dict hook."""
		return {decode_mapping[k] if strict or k in decode_mapping else k: v for k, v in src}

	return json.loads(src, object_pairs_hook=decoder)


def encoder(src: any, strict: bool = False) -> any:
	"""Convert keys recursively."""
	if isinstance(src, collections.abc.Mapping):
		return {encode_mapping[k] if strict or k in encode_mapping else k: encoder(v, strict=strict) for k, v in src.items()}
	if isinstance(src, (tuple, list)):
		return [encoder(v, strict=strict) for v in src]
	return src


def encode(src: any, strict: bool = False) -> str:
	"""Encode to json."""
	return json.dumps(encoder(src, strict=strict), separators=(',', ':'), ensure_ascii=False)


def to_json(data: bytes) -> str:
	"""Convert to valid json."""
	return data.strip(b'\x00').decode('iso-8859-15')


def from_json(data: str) -> bytes:
	"""Convert to bytes."""
	return data.encode('iso-8859-15') + b'\x00'


def uint32(data: bytes) -> int:
	"""Convert 4 bytes to a little endian unsigned integer."""
	return int.from_bytes(data, byteorder='little', signed=False) & 0xffffffff


def byte4(data: int) -> bytes:
	"""Convert unsigned 32 bit integer to 4 bytes."""
	return data.to_bytes(4, byteorder='little', signed=False)


def decompress(data: bytes) -> bytes:
	"""Decompresses the given save bytes."""
	size = len(data)
	din = io.BytesIO(data)
	out = bytearray()
	while din.tell() < size:
		magic = uint32(din.read(4))
		if magic != 0xfeeda1e5:
			print("Invalid Block, bad file (already decompressed?)")
			return data
		compressedSize = uint32(din.read(4))
		uncompressedSize = uint32(din.read(4))
		din.seek(4, 1)  # skip 4 bytes
		out += lz4.block.decompress(din.read(compressedSize), uncompressed_size=uncompressedSize)
	return out


def compress(data: bytes) -> bytes:
	"""Compresses the given save bytes."""
	chunk_size = 0x80000
	out = bytearray()
	for din in iter(data[i:i + chunk_size] for i in range(0, len(data), chunk_size)):
		block = lz4.block.compress(din, store_size=False)
		out += byte4(0xfeeda1e5)
		out += byte4(len(block))
		out += byte4(len(din))
		out += byte4(0)
		out += block
	return out


"""File picker logic."""


def file_save(file_name: Path):
	"""Save data struct to file, autodetecting format."""
	if file_name.suffix == '.json':
		file_name.write_text(json.dumps(data[0], separators=(',', ':'), ensure_ascii=False))
	else:
		file_name.write_bytes(compress(from_json(encode(data[0]))))


def cmd_save():
	"""[Event] Start filepicker in save mode."""
	fp: QFileDialog = wnd.file_picker
	fp.setFileMode(QFileDialog.AnyFile)
	fp.setAcceptMode(QFileDialog.AcceptSave)
	fp.accept_command = file_save
	fp.open()


def file_open(file_name: Path):
	"""Load a file into data struct and init tree view"""
	if file_name.suffix == '.json':
		data[0] = json.loads(file_name.read_text())
	else:
		data[0] = decode(to_json(decompress(file_name.read_bytes())))
	wnd.mTree.clear()
	itm = tree_add('root', (data, 0), wnd.mTree)
	itm.setExpanded(True)


def cmd_open():
	"""[Event] Start filepicker in open mode."""
	fp: QFileDialog = wnd.file_picker
	fp.setFileMode(QFileDialog.ExistingFile)
	fp.setAcceptMode(QFileDialog.AcceptOpen)
	fp.accept_command = file_open
	fp.open()


def file_picker_accept():
	"""[Event] User has selected a file."""
	fp: QFileDialog = wnd.file_picker
	fpath = Path(fp.selectedFiles()[0]).absolute()
	lst = fp.sidebarUrls()
	url = QUrl.fromLocalFile(fpath.parent)
	while url in lst:
		lst.remove(url)
	lst.insert(0, url)
	while len(lst) > 100:
		lst.pop()
	fp.setSidebarUrls(lst)
	fp.accept_command(fpath)


"""Tree and text logic."""


def txt_save(e: QFocusEvent):
	"""[Event] On focus loss, if user has changed json data, update data struct, tree and json display."""
	if wnd.mText.contentChanged and wnd.mText.curItem:
		wnd.mText.contentChanged = False
		try:
			dat = json.loads(wnd.mText.toPlainText())
		except Exception as err:
			print('json error:', repr(err))
			return
		itm: QTreeWidgetItem = wnd.mText.curItem
		accessor = itm.data(0, Qt.ItemDataRole.UserRole)
		accessor[0][accessor[1]] = dat
		tree_reset(itm, dat)
		txt_display(dat)


def txt_changed():
	"""[Event] Detect if user has changed json data."""
	wnd.mText.contentChanged = True


def txt_display(data: any):
	"""Format and display json data."""
	wnd.mText.clear()
	wnd.mText.setPlainText(json.dumps(data, indent='\t', ensure_ascii=False))
	wnd.mText.contentChanged = False


def tree_expand(item: QTreeWidgetItem):
	"""[Event] Add child nodes when a node is first expanded."""
	if item.childCount() <= 0:
		accessor = item.data(0, Qt.ItemDataRole.UserRole)
		item_data = accessor[0][accessor[1]]
		for k in item_data.keys() if isinstance(item_data, collections.abc.Mapping) else range(len(item_data)):
			tree_add(k if isinstance(k, str) else f"[{repr(k)}]", (item_data, k), item)


def tree_click(current: QTreeWidgetItem | None, previous: QTreeWidgetItem):
	"""[Event] Display json when selected node is changed."""
	if isinstance(current, QTreeWidgetItem):
		accessor = current.data(0, Qt.ItemDataRole.UserRole)
		txt_display(accessor[0][accessor[1]])
	wnd.mText.curItem = current


def tree_reset(itm: QTreeWidgetItem, data: any):
	"""Reset node according to data."""
	if itm.isExpanded():
		itm.setExpanded(False)
	for n in reversed(range(itm.childCount())):
		itm.removeChild(itm.child(n))
	itm.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator if isinstance(data, (collections.abc.Mapping, list)) else QTreeWidgetItem.DontShowIndicatorWhenChildless)


def tree_add(name: str, accessor: tuple[any, any], parent: QTreeWidgetItem):
	"""Add a node to tree list."""
	itm = QTreeWidgetItem(parent)
	itm.setText(0, name)
	itm.setData(0, Qt.ItemDataRole.UserRole, accessor)
	if isinstance(parent, QTreeWidgetItem):
		parent.addChild(itm)
	else:
		parent.addTopLevelItem(itm)
	tree_reset(itm, accessor[0][accessor[1]])
	return itm


"""config and main"""


def main(*args: str) -> int:
	global app
	global wnd
	app = QApplication(['NMSSGE'])
	wnd = QMainWindow()
	wnd.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / 'icon.png')))
	wnd.setWindowTitle("No Man's Sky SaveGame Editor")

	wnd.mainWidget = QWidget(parent=wnd)
	wnd.layMain = QVBoxLayout(wnd.mainWidget)
	wnd.layButtons = QHBoxLayout()
	wnd.layMain.addLayout(wnd.layButtons)
	wnd.btnOpen = QPushButton(text='&Open', parent=wnd.mainWidget)
	wnd.layButtons.addWidget(wnd.btnOpen)
	wnd.btnSave = QPushButton(text='&Save', parent=wnd.mainWidget)
	wnd.layButtons.addWidget(wnd.btnSave)
	wnd.layData = QSplitter(parent=wnd.mainWidget)
	wnd.layMain.addWidget(wnd.layData)
	wnd.mTree = QTreeWidget(parent=wnd.layData)
	wnd.layData.addWidget(wnd.mTree)
	wnd.mText = QPlainTextEdit(parent=wnd.layData)
	wnd.layData.addWidget(wnd.mText)

	wnd.file_picker = QFileDialog(wnd)
	wnd.file_picker.setDefaultSuffix('.hg')
	wnd.file_picker.setNameFilters(['Hello Games SaveFile (*.hg)', 'Java Script Object Notation (*.json)', 'Any (*)'])
	wnd.file_picker.setViewMode(QFileDialog.Detail)

	wnd.layData.setChildrenCollapsible(False)
	wnd.mTree.setColumnCount(1)
	wnd.mTree.setHeaderHidden(True)
	wnd.mText.setTabStopDistance(wnd.mText.fontMetrics().horizontalAdvance('\u2192'))
	wnd.mText.setLineWrapMode(QPlainTextEdit.NoWrap)
	wnd.setCentralWidget(wnd.mainWidget)

	wnd.file_picker.accepted.connect(file_picker_accept)
	wnd.btnOpen.pressed.connect(cmd_open)
	wnd.btnSave.pressed.connect(cmd_save)
	wnd.mTree.currentItemChanged.connect(tree_click)
	wnd.mTree.itemExpanded.connect(tree_expand)
	wnd.mText.textChanged.connect(txt_changed)
	wnd.mText.focusOutEvent = txt_save

	wnd.actnQuit = QAction(text='&Quit', parent=wnd)
	wnd.actnQuit.setShortcuts(["Ctrl+Q", 'ESC'])
	wnd.actnQuit.triggered.connect(wnd.close)
	wnd.addAction(wnd.actnQuit)

	settings = QSettings('SunBlade', 'NMSSGE')
	wnd.restoreGeometry(settings.value('geometry', QByteArray()))
	wnd.layData.restoreState(settings.value('splitter', QByteArray()))
	wnd.file_picker.restoreState(settings.value('fp_state', QByteArray()))
	wnd.file_picker.restoreGeometry(settings.value('fp_geometry', QByteArray()))
	wnd.file_picker.selectNameFilter(settings.value('fp_filter', ''))

	wnd.show()

	if len(args) > 0:
		file_open(Path(args[0]))

	app.exec()

	settings.setValue('geometry', wnd.saveGeometry())
	settings.setValue('splitter', wnd.layData.saveState())
	settings.setValue('fp_state', wnd.file_picker.saveState())
	settings.setValue('fp_geometry', wnd.file_picker.saveGeometry())
	settings.setValue('fp_filter', wnd.file_picker.selectedNameFilter())

	return 0


if __name__ == "__main__":
	sys.exit(main(*sys.argv[1:]))
