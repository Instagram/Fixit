import threading
import time
from unittest import TestCase

from fixit.util import debounce


class DebounceTest(TestCase):
    def test_delayed_execution(self):
        """Test if the decorated function is delayed by the debounce time."""
        executed = [False]

        @debounce(0.01)
        def f():
            executed[0] = True
            return True

        result = f()
        self.assertIsNone(result)
        self.assertFalse(executed[0])
        time.sleep(0.03)
        self.assertTrue(executed[0])

    def test_single_execution_after_multiple_calls(self):
        """Test if the decorated function is executed once after multiple rapid calls."""
        counter = [0]

        @debounce(0.01)
        def f():
            counter[0] += 1

        for _ in range(10):
            f()

        time.sleep(0.03)
        self.assertEqual(counter[0], 1)

    def test_thread_safety(self):
        """Test the thread safety of the decorated function."""
        counter = [0]

        @debounce(0.01)
        def f():
            counter[0] += 1

        threads = []
        for _ in range(10):
            t = threading.Thread(target=f)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        time.sleep(0.03)
        self.assertEqual(counter[0], 1)
