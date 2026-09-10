import unittest

from services.application_lifecycle import ApplicationLifecycle


class ShutdownResourceStub:
    def __init__(self) -> None:
        self.shutdown_calls = 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1


class BackgroundResourceStub:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


class TrayResourceStub(BackgroundResourceStub):
    def __init__(self, *, available: bool) -> None:
        super().__init__()
        self.available = available


class ApplicationLifecycleTests(unittest.TestCase):
    def build_lifecycle(self, *, tray_available: bool = True):
        speech_manager = ShutdownResourceStub()
        runtime_manager = ShutdownResourceStub()
        scheduler = ShutdownResourceStub()
        overlay = BackgroundResourceStub()
        tray = TrayResourceStub(available=tray_available)
        actions: list[str] = []
        lifecycle = ApplicationLifecycle(
            speech_manager=speech_manager,
            runtime_manager=runtime_manager,
            tray_service=tray,
            shutdown_resources=(scheduler,),
            background_resources=(overlay,),
            hide_window=lambda: actions.append("hide"),
            restore_window=lambda: actions.append("restore"),
            close_window=lambda: actions.append("close"),
        )
        return lifecycle, speech_manager, runtime_manager, scheduler, overlay, tray, actions

    def test_request_close_hides_window_when_tray_is_available(self) -> None:
        lifecycle, speech, runtime, scheduler, overlay, tray, actions = (
            self.build_lifecycle()
        )

        lifecycle.request_close()

        self.assertEqual(["hide"], actions)
        self.assertEqual(0, speech.shutdown_calls)
        self.assertEqual(0, runtime.shutdown_calls)
        self.assertEqual(0, scheduler.shutdown_calls)
        self.assertEqual(0, overlay.stop_calls)
        self.assertEqual(0, tray.stop_calls)

    def test_request_close_closes_window_when_tray_is_unavailable(self) -> None:
        lifecycle, *_resources, actions = self.build_lifecycle(
            tray_available=False
        )

        lifecycle.request_close()

        self.assertEqual(["close"], actions)

    def test_exit_application_stops_every_resource_only_once(self) -> None:
        lifecycle, speech, runtime, scheduler, overlay, tray, actions = (
            self.build_lifecycle()
        )

        lifecycle.exit_application()
        lifecycle.exit_application()

        self.assertEqual(1, speech.shutdown_calls)
        self.assertEqual(1, runtime.shutdown_calls)
        self.assertEqual(1, scheduler.shutdown_calls)
        self.assertEqual(1, overlay.stop_calls)
        self.assertEqual(1, tray.stop_calls)
        self.assertEqual(["close"], actions)

    def test_restore_delegates_to_window_callback(self) -> None:
        lifecycle, *_resources, actions = self.build_lifecycle()

        lifecycle.restore()

        self.assertEqual(["restore"], actions)


if __name__ == "__main__":
    unittest.main()
