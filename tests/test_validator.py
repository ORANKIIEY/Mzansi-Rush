import unittest
import copy
import os
import sys

# Add src to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.validator import validate_track, load_json_file

class TestRacetrackValidator(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.schema_path = os.path.join(self.base_dir, "data", "world_schema.json")
        self.tile_defs_path = os.path.join(self.base_dir, "data", "tile_definitions.json")
        self.sample_track_path = os.path.join(self.base_dir, "data", "sample_base.json")
        self.valid_data = load_json_file(self.sample_track_path)

    def test_valid_track_passes(self):
        res = validate_track(self.valid_data, self.schema_path, self.tile_defs_path)
        self.assertTrue(res["valid"], f"Expected track to be valid, but got errors: {res['errors']}")

    def test_mismatched_grid_dimensions(self):
        # Height mismatch
        data = copy.deepcopy(self.valid_data)
        data["grid_size"]["height"] = 11  # Grid actually has 10 rows
        res = validate_track(data, self.schema_path, self.tile_defs_path)
        self.assertFalse(res["valid"])
        self.assertTrue(any("Grid height mismatch" in err for err in res["errors"]))

        # Width mismatch
        data = copy.deepcopy(self.valid_data)
        data["grid"][0] = "WWWW"  # Too short
        res = validate_track(data, self.schema_path, self.tile_defs_path)
        self.assertFalse(res["valid"])
        self.assertTrue(any("Grid width mismatch" in err for err in res["errors"]))

    def test_invalid_tile_character(self):
        data = copy.deepcopy(self.valid_data)
        # Modify a tile character to an unmapped 'X'
        row_list = list(data["grid"][1])
        row_list[1] = "X"
        data["grid"][1] = "".join(row_list)
        res = validate_track(data, self.schema_path, self.tile_defs_path)
        self.assertFalse(res["valid"])
        self.assertTrue(any("undefined character: 'X'" in err for err in res["errors"]))

    def test_non_sequential_checkpoints(self):
        data = copy.deepcopy(self.valid_data)
        # Change checkpoint IDs from 1,2,3,4 to 1,3,4,5 (skipping 2)
        data["checkpoints"][1]["id"] = 5
        res = validate_track(data, self.schema_path, self.tile_defs_path)
        self.assertFalse(res["valid"])
        self.assertTrue(any("Checkpoint IDs must be sequential" in err for err in res["errors"]))

    def test_checkpoint_on_non_drivable_tile(self):
        data = copy.deepcopy(self.valid_data)
        # Place checkpoint 2 (originally x=13, y=5) on a Wall (W)
        # Change tile at x=13, y=5 to 'W'
        row_list = list(data["grid"][5])
        row_list[13] = "W"
        data["grid"][5] = "".join(row_list)
        res = validate_track(data, self.schema_path, self.tile_defs_path)
        self.assertFalse(res["valid"])
        self.assertTrue(any("non-drivable tile" in err for err in res["errors"]))

    def test_blocked_track_routing_fails(self):
        data = copy.deepcopy(self.valid_data)
        # Block the road at x=7, y=1 (Start/Finish Line location) by surrounding it with Walls
        # This will block Checkpoint 1 (x=7, y=1) from Checkpoint 2
        # Let's change the asphalt tiles around checkpoint 1 to Wall
        # Row 1 is: WAAAAAAAAAAAAAW (checkpoint at idx 7)
        row_list = list(data["grid"][1])
        row_list[6] = "W"
        row_list[8] = "W"
        data["grid"][1] = "".join(row_list)
        
        res = validate_track(data, self.schema_path, self.tile_defs_path)
        self.assertFalse(res["valid"])
        self.assertTrue(any("Connectivity check failed" in err for err in res["errors"]))

if __name__ == "__main__":
    unittest.main()
