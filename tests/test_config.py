
from dustcluster.config  import DustConfig

import shutil
import unittest
import mock
import os

from dustcluster import util
logger = util.setup_logger( __name__ )

import logging

class TestConfig(unittest.TestCase):

    testdirs = '/tmp/dusttest'

    def setUp(self):
        logger.setLevel(logging.DEBUG)
        logging.getLogger('dustcluster.config').setLevel(logging.DEBUG)
        DustConfig.dust_dir = self.testdirs

    @unittest.skip("port to v0.2")
    def test_first_use(self):

        if os.path.exists(self.testdirs) and self.testdirs.startswith('/tmp'):
            shutil.rmtree(self.testdirs)

        config = DustConfig()

    @unittest.skip("port to v0.2")
    def test_second_use(self):

        config = DustConfig()

if __name__ == "__main__":
    unittest.main()

