import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.connectors.bingx_websocket import BingXWebSocket
import pandas as pd

class TestWebSocket(unittest.TestCase):
    def test_callback_execution(self):
        # 1. Setup Mock Callbacks
        mock_depth_cb = AsyncMock()
        mock_kline_cb = AsyncMock()

        ws = BingXWebSocket("XAU/USDT", mock_depth_cb, mock_kline_cb)

        # 2. Simulate Incoming Message (Depth)
        # Assuming msg is parsed JSON
        # We need to test _handle_message logic

        # Create a mock data structure that matches _handle_message expectation
        depth_payload = {
            "dataType": "XAU-USDT@depth20",
            "data": {
                "bids": [["2000.0", "1.5"], ["1999.0", "2.0"]],
                "asks": [["2001.0", "1.0"], ["2002.0", "0.5"]]
            }
        }

        import json
        async def run_test():
            await ws._handle_message(json.dumps(depth_payload))

        asyncio.run(run_test())

        # 3. Verify Callback called
        mock_depth_cb.assert_called_once()

        # Check arguments passed to callback
        args, _ = mock_depth_cb.call_args
        bids, asks = args
        self.assertIsInstance(bids, pd.DataFrame)
        self.assertEqual(bids.iloc[0]['price'], 2000.0)

if __name__ == '__main__':
    unittest.main()
