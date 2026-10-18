"""Block 6 kiosk tile persistence, permissions and browser editing regression."""
import tempfile
import unittest
from pathlib import Path
from itomiscan.storage.config import ConfigStore, ConfigError
from itomiscan.storage.kiosk_tiles import TileError

def tile(label="Paperless", **overrides):
    value={"label":label, "action":"scan", "icon":"archive",
           "color":"#397edb", "parent":None, "targets":[],
           "background":False,
           "scan":{"source":"ADF Duplex","mode":"Color",
                   "resolution":300,"output":"PDF"}}
    value.update(overrides)
    return value


class TileStoreTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db=ConfigStore(Path(temp.name)/"itomiscan.db")
        self.db.save_target({"kind":"paperless","name":"DMS",
                             "address":"https://paperless.example"})
        self.db.save_target({"kind":"network","name":"NAS",
                             "address":"smb://nas.local/scans"})
        self.ids=[x["id"] for x in self.db.list_targets()]

    def test_custom_scan_button_with_two_targets(self):
        self.db.save_kiosk_tile(tile(targets=self.ids,background=True))
        item=self.db.list_kiosk_tiles()[0]
        self.assertEqual(item["targets"],self.ids)
        self.assertEqual(item["scan"]["resolution"],300)
        self.assertTrue(item["background"])
        self.assertEqual(item["color"],"#397edb")
        self.db.save_kiosk_tile(tile("Neu",targets=self.ids[:1]),item["id"])
        self.assertEqual(self.db.list_kiosk_tiles()[0]["label"],"Neu")
        with self.assertRaises(ConfigError):
            self.db.delete_target(self.ids[0])
        self.db.delete_kiosk_tile(item["id"])
        self.db.delete_target(self.ids[0])

    def test_config_export_restores_targets_and_group_links(self):
        self.db.save_kiosk_tile(tile("Büro",action="group",icon="folder",scan={}))
        group=self.db.list_kiosk_tiles()[0]["id"]
        self.db.save_kiosk_tile(tile("Beide",parent=group,targets=self.ids))
        backup=self.db.backup()
        self.assertEqual({tuple(x) for x in backup["kiosk_tiles"][1]["targets"]},
                         {("paperless","DMS"),("network","NAS")})
        self.db.restore(backup)
        tiles=self.db.list_kiosk_tiles()
        self.assertEqual(len(tiles),2)
        self.assertEqual(tiles[1]["parent"],tiles[0]["id"])
        self.assertEqual(set(tiles[1]["targets"]),
                         {t["id"] for t in self.db.list_targets()})
        broken=dict(backup)
        broken["kiosk_tiles"]=[dict(backup["kiosk_tiles"][1],
                                    targets=[["paperless","MISSING"]])]
        with self.assertRaises(ConfigError):
            self.db.restore(broken)
        self.assertEqual(self.db.list_kiosk_tiles(),tiles)

    def test_restore_old_backup_without_tiles_keeps_compatibility(self):
        old=self.db.backup()
        old.pop("kiosk_tiles",None)
        self.db.restore(old)
        self.assertEqual(self.db.list_kiosk_tiles(),[])
    def test_group_reorder_and_single_level(self):
        self.db.save_kiosk_tile(tile("Büro",action="group",icon="folder",
                                     targets=[],scan={}))
        ident=self.db.list_kiosk_tiles()[0]["id"]
        self.db.save_kiosk_tile(tile("Archiv",parent=ident))
        with self.assertRaises(TileError):
            self.db.delete_kiosk_tile(ident)
        with self.assertRaises(TileError):
            self.db.save_kiosk_tile(tile("Weitere Gruppe",action="group",
                                         icon="folder",parent=ident,scan={}))
        # The invalid nested group is rejected, preserving existing entries.
        self.assertEqual(len(self.db.list_kiosk_tiles()),2)

    def test_invalid_foreign_target_color_and_scan_settings(self):
        with self.assertRaises(TileError):
            self.db.save_kiosk_tile(tile(targets=[999999]))
        with self.assertRaises(TileError):
            self.db.save_kiosk_tile(tile(color="red;"))
        with self.assertRaises(ValueError):
            self.db.save_kiosk_tile(tile(scan={"resolution":10000}))


if __name__=="__main__":
    unittest.main()
