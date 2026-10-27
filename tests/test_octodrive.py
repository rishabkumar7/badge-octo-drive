"""Host-side checks for Octo Drive rules, assets and app states."""

import builtins
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

from PIL import Image


APP = Path(__file__).resolve().parents[1] / "octo_drive"
SPEC = importlib.util.spec_from_file_location("octo_drive_logic", APP / "game.py")
game = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(game)
DT = 1 / 30


class OctoDriveTests(unittest.TestCase):
    def test_track_and_checkpoints_cover_the_course(self):
        self.assertEqual(game.CHECKPOINTS[-1], game.TRACK_LENGTH)
        self.assertEqual(tuple(sorted(game.CHECKPOINTS)), game.CHECKPOINTS)
        self.assertGreater(game.TRACK_LENGTH, 5000)
        for distance in (0, game.TRACK_LENGTH / 2, game.TRACK_LENGTH - 1):
            name, curve, hill = game.track_at(distance)
            self.assertTrue(name)
            self.assertLessEqual(abs(curve), 1)
            self.assertLessEqual(abs(hill), 1)

    def test_accelerating_braking_and_offroad_drag(self):
        world = game.World()
        controls = game.Controls()
        controls.accelerate = True
        for _ in range(120):
            world.step(DT, controls)
        self.assertGreater(world.speed, 100)
        accelerated = world.speed
        controls.accelerate = False
        controls.brake = True
        for _ in range(15):
            world.step(DT, controls)
        self.assertLess(world.speed, accelerated)
        world.speed = game.MAX_SPEED
        world.lane = 1.2
        controls.brake = False
        world.step(DT, controls)
        self.assertLess(world.speed, game.MAX_SPEED)

    def test_checkpoints_add_time_and_finish(self):
        world = game.World()
        controls = game.Controls()
        world.distance = game.CHECKPOINTS[0] - 1
        world.speed = 120
        before = world.time_left
        world.step(DT, controls)
        self.assertEqual(world.next_checkpoint, 1)
        self.assertGreater(world.time_left, before)
        world.distance = game.TRACK_LENGTH - 1
        world.speed = 120
        world.next_checkpoint = len(game.CHECKPOINTS) - 1
        world.step(DT, controls)
        self.assertEqual(world.state, "finished")
        self.assertEqual(world.distance, game.TRACK_LENGTH)
        self.assertIsNotNone(world.session.best_time)

    def test_collision_slows_player_and_passing_scores(self):
        world = game.World()
        car = world.traffic[0]
        car.distance = 100
        car.lane = 0
        car.speed = 50
        world.distance = 94
        world.speed = 180
        world.step(DT, game.Controls())
        self.assertLess(world.speed, 100)
        self.assertTrue(car.collided)
        self.assertTrue(any(event[0] == "collision" for event in world.events))
        world.collision_time = 0
        world.events = []
        car.distance = world.distance + 1
        world.speed = 180
        world.step(DT, game.Controls())
        self.assertFalse(any(event[0] == "collision" for event in world.events))
        world.events = []
        car.distance = world.distance + 1
        car.speed = 0
        world.speed = 100
        car.passed = False
        world.step(DT, game.Controls())
        self.assertTrue(car.passed)
        self.assertTrue(any(event[0] == "pass" for event in world.events))

    def test_timer_ends_race(self):
        world = game.World()
        world.time_left = DT / 2
        world.step(DT, game.Controls())
        self.assertEqual(world.state, "time_up")
        self.assertEqual(world.speed, 0)

    def test_obstacle_density_increases_each_quarter(self):
        traffic = []
        hazards = []
        world = game.World()
        for quarter in range(4):
            start = quarter * game.QUARTER_LENGTH
            end = start + game.QUARTER_LENGTH
            traffic.append(sum(start <= car.distance < end for car in world.traffic))
            hazards.append(sum(start <= hazard.distance < end for hazard in world.hazards))
        self.assertEqual(traffic, sorted(traffic))
        self.assertEqual(hazards, sorted(hazards))
        self.assertEqual(traffic, list(game.TRAFFIC_COUNTS))
        self.assertEqual(hazards, list(game.HAZARD_COUNTS))

    def test_barrier_collision_slows_player(self):
        world = game.World()
        barrier = game.Hazard(100, 0, "barrier")
        world.hazards = [barrier]
        world.traffic = []
        world.distance = 96
        world.speed = 120
        world.step(DT, game.Controls())
        self.assertTrue(barrier.hit)
        self.assertLess(world.speed, 60)
        self.assertTrue(any(event == ("hazard", "barrier") for event in world.events))

    def test_course_can_be_finished_under_timer(self):
        world = game.World()
        controls = game.Controls()
        controls.accelerate = True
        for _ in range(30 * 180):
            controls.left = world.lane > 0.12
            controls.right = world.lane < -0.12
            world.step(DT, controls)
            if world.state != "play":
                break
        self.assertEqual(world.state, "finished")
        self.assertGreater(world.time_left, 0)
        self.assertLessEqual(abs(world.lane), 1)

    def test_asset_sizes(self):
        sizes = {"icon.png": (24, 24), "assets/players.png": (128, 128)}
        for name, size in sizes.items():
            with Image.open(APP / name) as asset:
                self.assertEqual(asset.size, size, name)


class Anything:
    width = 160
    height = 120

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return Anything()

    def __call__(self, *args, **kwargs):
        return Anything()

    def __or__(self, other):
        return self

    def __iter__(self):
        return iter((40, 10))


class FakeBadge(Anything):
    def __init__(self):
        self.ticks = 0
        self.ticks_delta = 33
        self.down = set()
        self.fresh = set()

    def pressed(self, button=None):
        if button is None:
            return set(self.fresh)
        return button in self.fresh

    def held(self, button):
        return button in self.down

    def frame(self, buttons=(), hold=()):
        self.fresh = set(buttons)
        self.down = set(buttons) | set(hold)
        self.ticks += self.ticks_delta


class AppStateTests(unittest.TestCase):
    def test_app_runs_through_every_screen(self):
        names = ("UP", "DOWN", "LEFT", "RIGHT", "SELECT", "BACK", "MENU", "HOME")
        fake = FakeBadge()
        saved = {}
        state_mod = types.ModuleType("badgeware")
        state_mod.State = types.SimpleNamespace(
            load=lambda name, data: None,
            save=lambda name, data: saved.update(data),
        )
        runtime = {
            "badge": fake, "screen": Anything(), "image": Anything(), "font": Anything(),
            "color": Anything(), "vec2": Anything, "rect": Anything, "LORES": Anything(),
            "VSYNC": Anything(), "is_dir": lambda path: path == "/octo_drive",
            "run": lambda update: None,
        }
        for name in names:
            runtime["BUTTON_" + name] = name
        old_modules = dict(sys.modules)
        old_path = list(sys.path)
        added = [key for key in runtime if not hasattr(builtins, key)]
        sys.modules["badgeware"] = state_mod
        sys.modules["game"] = game
        sys.path.insert(0, str(APP))
        for key, value in runtime.items():
            setattr(builtins, key, value)
        chdir = mock.patch("os.chdir")
        chdir.start()
        try:
            for module in ("render", "octo_drive_app"):
                sys.modules.pop(module, None)
            spec = importlib.util.spec_from_file_location("octo_drive_app", APP / "__init__.py")
            app = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(app)

            def frames(count, buttons=(), hold=()):
                for _ in range(count):
                    fake.frame(buttons, hold)
                    app.update()
                    fake.frame((), hold)

            frames(2)
            self.assertEqual(app.state, app.TITLE)
            frames(1, ("SELECT",))
            self.assertEqual(app.state, app.COUNTDOWN)
            frames(110)
            self.assertEqual(app.state, app.PLAY)
            frames(15, hold=("SELECT", "RIGHT"))
            self.assertGreater(app.world.speed, 0)
            frames(1, ("MENU",))
            self.assertEqual(app.state, app.PAUSE)
            frames(1, ("BACK",))
            self.assertEqual(app.state, app.PLAY)
            app.world.time_left = 0.01
            frames(1)
            self.assertEqual(app.state, app.OVER)
            frames(30)
            frames(1, ("SELECT",))
            self.assertEqual(app.state, app.TITLE)
            app.new_game()
            app.set_state(app.PLAY)
            app.world.distance = game.TRACK_LENGTH - 1
            app.world.next_checkpoint = len(game.CHECKPOINTS) - 1
            app.world.speed = 120
            frames(1, hold=("SELECT",))
            self.assertEqual(app.state, app.WIN)
            app.on_exit()
            self.assertGreaterEqual(saved["high"], 0)
        finally:
            chdir.stop()
            sys.path[:] = old_path
            for key in added:
                delattr(builtins, key)
            sys.modules.clear()
            sys.modules.update(old_modules)


if __name__ == "__main__":
    unittest.main()
