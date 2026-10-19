"""Beta 6: updater dialog must remain dismissible during a running update.

The UI runs on the real Tk kiosk; these source-level checks supplement the
graphical regression workflow without needing hardware or a display.
"""
import inspect
import unittest
from itomiscan.gui.beta_updates import BetaUpdateDialog


class UpdateDialogTests(unittest.TestCase):
    def test_close_is_independent_of_worker_state(self):
        class FakeWindow:
            destroyed = False
            def destroy(self):
                self.destroyed = True

        dialog = BetaUpdateDialog.__new__(BetaUpdateDialog)
        dialog.dialog = FakeWindow()
        dialog.working = True
        dialog.close()
        self.assertTrue(dialog.dialog.destroyed)

    def test_update_close_control_remains_enabled_during_install(self):
        source = inspect.getsource(BetaUpdateDialog.run_helper)
        disabling = source.split("button.configure(state=tk.DISABLED)", 1)[0]
        self.assertNotIn("self.close_button", disabling)
        self.assertNotIn("self.header_close_button", disabling)
        self.assertIn("self.app.busy = False", source)

    def test_background_progress_updates_kiosk_status_even_after_close(self):
        class App:
            def __init__(self):
                self.status_var = self
                self.last = None
            def set(self, value):
                self.last = value
            def dispatch(self, callback):
                callback()
        class Closed:
            def winfo_exists(self):
                return False
        dialog = BetaUpdateDialog.__new__(BetaUpdateDialog)
        dialog.app = App()
        dialog.dialog = Closed()
        dialog.publish("Installiert: erfolgreich", 100)
        self.assertEqual(dialog.app.last, "Installiert: erfolgreich")


if __name__ == "__main__":
    unittest.main()
