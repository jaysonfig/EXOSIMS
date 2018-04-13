#!/usr/local/bin/python
#
# Usage:
#   run from shell, or
#   % python <this_file.py>

r"""TimeKeeping module unit tests

Michael Turmon, JPL, Mar/Apr 2016
"""

import sys
import unittest
import StringIO
from collections import namedtuple
import EXOSIMS.OpticalSystem
import EXOSIMS.SurveySimulation
import pkgutil
from EXOSIMS.Prototypes.TimeKeeping import TimeKeeping
from EXOSIMS.Prototypes.Observatory import Observatory
from EXOSIMS.Prototypes.OpticalSystem import OpticalSystem
from tests.TestSupport.Utilities import RedirectStreams
from EXOSIMS.Prototypes.SurveySimulation import SurveySimulation
from tests.TestSupport.Info import resource_path
from EXOSIMS.util.get_module import get_module
import os
import numpy as np
import astropy.units as u
from astropy.time import Time
import pdb

class TestTimeKeepingMethods(unittest.TestCase):
    r"""Test TimeKeeping class."""

    def setUp(self):
        # print '[setup] ',
        # do not instantiate it
        self.fixture = TimeKeeping

        self.dev_null = open(os.devnull, 'w')
        self.script1 = resource_path('test-scripts/simplest.json')
        self.script2 = resource_path('test-scripts/simplest_initOB.json')
    
        modtype = getattr(SurveySimulation,'_modtype')
        self.allmods = [get_module(modtype)]

    def tearDown(self):
        pass

    def test_init(self):
        r"""Test of initialization and __init__.
        """
        tk = self.fixture()
        self.assertEqual(tk.currentTimeNorm.to(u.day).value, 0.0)
        self.assertEqual(type(tk._outspec), type({}))
        # check for presence of one class attribute
        self.assertGreater(tk.missionLife.value, 0.0)

        exclude_mods=['KnownRVSurvey', 'ZodiacalLight','BackgroundSources', 'Completeness'\
        'PlanetPhysicalModel', 'PlanetPopulation', 'PostProcessing']

        required_modules = [\
            'Observatory', 'OpticalSystem',\
            'SimulatedUniverse', 'TargetList', 'TimeKeeping']
        
        for mod in self.allmods:
            if mod.__name__ in exclude_mods:
                continue
            
            with RedirectStreams(stdout=self.dev_null):
                sim = mod(scriptfile=self.script1)

            self.assertIsInstance(sim._outspec, dict)
            # check for presence of a couple of class attributes
            self.assertIn('DRM', sim.__dict__)

            for rmod in required_modules:
                self.assertIn(rmod, sim.__dict__)
                self.assertEqual(getattr(sim,rmod)._modtype,rmod)

    def test_str(self):
        r"""Test __str__ method, for full coverage."""
        tk = self.fixture()
        # replace stdout and keep a reference
        original_stdout = sys.stdout
        sys.stdout = StringIO.StringIO()
        # call __str__ method
        result = tk.__str__()
        # examine what was printed
        contents = sys.stdout.getvalue()
        self.assertEqual(type(contents), type(''))
        self.assertIn('currentTimeNorm', contents)
        sys.stdout.close()
        # it also returns a string, which is not necessary
        self.assertEqual(type(result), type(''))
        # put stdout back
        sys.stdout = original_stdout

    def test_initOB(self):
        r"""Test init_OB method
            Strategy is to test Observing Blocks loaded from a file, then test automatically defined OB
        """
        tk = self.fixture()

        # 1) Load Observing Blocks from File
        OBduration = np.inf
        tk.init_OB('sampleOB.csv',OBduration*u.d)#File Located in: EXOSIMS/EXOSIMS/Scripts/sampleOB.csv
        self.assertTrue(tk.OBduration == OBduration*u.d)
        self.assertTrue(tk.OBnumber == 0)
        self.assertTrue(set(tk.OBstartTimes) == set([0,40,80,120,160,200,240,280,320,360]*u.d))
        self.assertTrue(set(tk.OBendTimes) == set([20,60,100,140,180,220,260,300,340,380]*u.d))

        # 2) Automatically construct OB from OBduration, missionLife, and missionPortion SINGLE BLOCK
        OBduration = 10
        tk.missionLife = 100*u.d
        tk.missionPortion = 0.1
        tk.init_OB(str(None), OBduration*u.d)
        self.assertTrue(tk.OBduration == OBduration*u.d)
        self.assertTrue(tk.OBnumber == 0)
        self.assertTrue(len(tk.OBendTimes) == 1)
        self.assertTrue(len(tk.OBstartTimes) == 1)
        self.assertTrue(tk.OBstartTimes[0] == 0*u.d)
        self.assertTrue(tk.OBendTimes[0] == OBduration*u.d)

        # 3) Automatically construct OB from OBduration, missionLife, and missionPortion TWO BLOCK
        OBduration = 10
        tk.missionLife = 100*u.d
        tk.missionPortion = 0.2
        tk.init_OB(str(None), OBduration*u.d)
        self.assertTrue(tk.OBduration == OBduration*u.d)
        self.assertTrue(tk.OBnumber == 0)
        self.assertTrue(len(tk.OBendTimes) == 2)
        self.assertTrue(len(tk.OBstartTimes) == 2)
        self.assertTrue(set(tk.OBstartTimes) == set([0,50]*u.d))
        self.assertTrue(set(tk.OBendTimes) == set([OBduration, 50 + OBduration]*u.d))

    def test_allocate_time(self):
        r"""Test allocate_time method.

        Approach: Ensure erraneous time allocations fail and time allocations exceeding mission constraints fail
        """
        tk = self.fixture(OBduration=10.0)

        # 1) dt = 0: All time allocation should fail
        tmpcurrentTimeAbs = tk.currentTimeAbs.copy()
        tmpcurrentTimeNorm = tk.currentTimeNorm.copy()
        tmpexoplanetObsTime = tk.exoplanetObsTime.copy()
        self.assertFalse(tk.allocate_time(0*u.d,True))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)
        self.assertFalse(tk.allocate_time(0*u.d,False))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)

        # 2) dt < 0: All time allocation should fail
        tmpcurrentTimeAbs = tk.currentTimeAbs.copy()
        tmpcurrentTimeNorm = tk.currentTimeNorm.copy()
        tmpexoplanetObsTime = tk.exoplanetObsTime.copy()
        self.assertFalse(tk.allocate_time(-1*u.d,True))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)
        self.assertFalse(tk.allocate_time(-1*u.d,False))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)

        # 3) Exceeds missionLife: All time allocation should fail
        tk.missionLife = 365*u.d
        tk.currentTimeNorm = tk.missionLife - 1*u.d
        tk.currentTimeAbs = tk.missionStart + tk.currentTimeNorm
        tmpcurrentTimeAbs = tk.currentTimeAbs.copy()
        tmpcurrentTimeNorm = tk.currentTimeNorm.copy()
        tmpexoplanetObsTime = tk.exoplanetObsTime.copy()
        self.assertFalse(tk.allocate_time(2*u.d,True))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)
        self.assertFalse(tk.allocate_time(2*u.d,False))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)
        tk.currentTimeNorm = 0*u.d
        tk.currentTimeAbs = tk.missionStart

        # 4) Exceeds current OB: All time allocation should fail
        tk.OBendTimes = [20]*u.d
        tk.OBnumber = 0
        tk.currentTimeNorm = tk.OBendTimes[tk.OBnumber] - 1*u.d
        tk.currentTimeAbs = tk.missionStart + tk.currentTimeNorm
        tmpcurrentTimeAbs = tk.currentTimeAbs.copy()
        tmpcurrentTimeNorm = tk.currentTimeNorm.copy()
        tmpexoplanetObsTime = tk.exoplanetObsTime.copy()
        self.assertFalse(tk.allocate_time(2*u.d,True))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)
        self.assertFalse(tk.allocate_time(2*u.d,False))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)
        tk.currentTimeNorm = 0*u.d
        tk.currentTimeAbs = tk.missionStart

        # 5a) Exceeds exoplanetObsTime: All time allocation should fail with add Exoplanet Obs Time is True
        tk.missionLife = 10*u.d
        tk.missionPortion = 0.2
        tk.OBendTimes = [10]*u.d
        tk.exoplanetObsTime = tk.missionLife*tk.missionPortion - 1*u.d
        tk.currentTimeNorm = tk.missionLife*tk.missionPortion - 1*u.d
        tk.currentTimeAbs = tk.missionStart + tk.currentTimeNorm
        tmpcurrentTimeAbs = tk.currentTimeAbs.copy()
        tmpcurrentTimeNorm = tk.currentTimeNorm.copy()
        tmpexoplanetObsTime = tk.exoplanetObsTime.copy()
        self.assertFalse(tk.allocate_time(2*u.d,True))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)

        # 5b) allocate_time with addExoplanetObsTime == False flag
        self.assertTrue(tk.allocate_time(2*u.d,False))
        self.assertFalse(tk.currentTimeAbs == tmpcurrentTimeAbs)
        self.assertFalse(tk.currentTimeNorm == tmpcurrentTimeNorm)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)

        # 6a) allocate_time successful under nominal conditions with addExoplanetObsTime == True
        tk.missionLife = 20*u.d
        tk.missionPortion = 1
        tk.OBendTimes = [20]*u.d
        tk.OBnumber = 0
        tk.currentTimeNorm = 0*u.d
        tk.currentTimeAbs = tk.missionStart + tk.currentTimeNorm
        tk.exoplanetObsTime = 0*u.d
        tmpcurrentTimeAbs = tk.currentTimeAbs.copy()
        tmpcurrentTimeNorm = tk.currentTimeNorm.copy()
        tmpexoplanetObsTime = tk.exoplanetObsTime.copy()
        self.assertTrue(tk.allocate_time(2*u.d,True))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs + 2*u.d)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm + 2*u.d)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime + 2*u.d)

        # 6b) allocate_time successful under nominal conditions with addExoplanetObsTime == True
        tmpcurrentTimeAbs = tk.currentTimeAbs.copy()
        tmpcurrentTimeNorm = tk.currentTimeNorm.copy()
        tmpexoplanetObsTime = tk.exoplanetObsTime.copy()
        self.assertTrue(tk.allocate_time(2*u.d,False))
        self.assertTrue(tk.currentTimeAbs == tmpcurrentTimeAbs + 2*u.d)
        self.assertTrue(tk.currentTimeNorm == tmpcurrentTimeNorm + 2*u.d)
        self.assertTrue(tk.exoplanetObsTime == tmpexoplanetObsTime)

    def test_mission_is_over(self):
        r"""Test mission_is_over method.

        Approach: Allocate time until mission completes.  Check that the mission terminated at
        the right time.
        """
        life = 0.1 * u.year
        tk = self.fixture(missionLife=life.to(u.year).value, missionPortion=1.0)
        sim = self.allmods[0](scriptfile=self.script1)
        allModes = sim.OpticalSystem.observingModes
        Obs = sim.Observatory
        det_mode = filter(lambda mode: mode['detectionMode'] == True, allModes)[0]

        # 1) mission not over
        tk.exoplanetObsTime = 0*u.d
        tk.currentTimeAbs = tk.missionStart
        tk.currentTimeNorm = 0*u.d
        self.assertFalse(tk.mission_is_over(Obs, det_mode)) #the mission has just begun

        # 2) exoplanetObsTime exceeded
        tk.exoplanetObsTime = 1.1*tk.missionLife*tk.missionPortion # set exoplanetObsTime to failure condition
        self.assertTrue(tk.mission_is_over(Obs, det_mode))
        tk.exoplanetObsTime = 0.*tk.missionLife*tk.missionPortion # reset exoplanetObsTime

        # 3) missionLife exceeded
        tk.currentTimeNorm = 1.1*tk.missionLife
        tk.currentTimeAbs = tk.missionStart + 1.1*tk.missionLife
        self.assertTrue(tk.mission_is_over(Obs, det_mode))
        tk.currentTimeNorm = 0*u.d
        tk.currentTimeAbs = tk.missionStart

        # 4) OBendTimes Exceeded
        tk.OBendTimes = [10]*u.d
        tk.OBnumber = 0
        tk.currentTimeNorm = tk.OBendTimes[tk.OBnumber] + 1*u.d
        tk.currentTimeAbs = tk.missionStart + tk.currentTimeNorm
        self.assertTrue(tk.mission_is_over(Obs, det_mode))
        tk.currentTimeAbs = 0*u.d
        tk.currentTimeAbs = tk.missionStart

    def test_advancetToStartOfNextOB(self):
        r""" Test advancetToStartOfNextOB method
        """  
        life = 2.0*u.year
        obdur = 15
        missPor = 0.6
        tk = self.fixture(missionLife=life.to(u.year).value, OBduration=obdur, missionPortion=missPor)

        tNowNorm1 = tk.currentTimeNorm.copy()
        tNowAbs1 = tk.currentTimeAbs.copy()
        OBnumstart = tk.OBnumber #get initial OB number
        tStart1 = tk.OBstartTimes[tk.OBnumber].copy()
        tk.advancetToStartOfNextOB()
        OBnumend = tk.OBnumber
        tStart2 = tk.OBstartTimes[tk.OBnumber].copy()
        tNowNorm2 = tk.currentTimeNorm.copy()
        tNowAbs2 = tk.currentTimeAbs.copy()
        self.assertEqual(OBnumend-OBnumstart,1)#only one observation block has been incremented

        self.assertEqual((tStart2-tStart1).value,obdur/missPor)#The mission advances
        self.assertEqual((tNowNorm2-tNowNorm1).value,obdur/missPor)
        self.assertEqual((tNowAbs2-tNowAbs1).value,obdur/missPor)


if __name__ == '__main__':
    unittest.main()
