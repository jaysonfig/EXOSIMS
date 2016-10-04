# -*- coding: utf-8 -*-
import numpy as np
import sys, logging
import astropy.units as u
import astropy.constants as const
from EXOSIMS.util.get_module import get_module

# the EXOSIMS logger
Logger = logging.getLogger(__name__)

class SurveySimulation(object):
    """Survey Simulation class template
    
    This class contains all variables and methods necessary to perform
    Survey Simulation Module calculations in exoplanet mission simulation.
    
    It inherits the following class objects which are defined in __init__:
    Simulated Universe, Observatory, TimeKeeping, PostProcessing
    
    Args:
        \*\*specs:
            user specified values
            
    Attributes:
        PlanetPopulation (PlanetPopulation module):
            PlanetPopulation class object
        PlanetPhysicalModel (PlanetPhysicalModel module):
            PlanetPhysicalModel class object
        OpticalSystem (OpticalSystem module):
            OpticalSystem class object
        ZodiacalLight (ZodiacalLight module):
            ZodiacalLight class object
        BackgroundSources (BackgroundSources module):
            BackgroundSources class object
        PostProcessing (PostProcessing module):
            PostProcessing class object
        Completeness (Completeness module):
            Completeness class object
        TargetList (TargetList module):
            TargetList class object
        SimulatedUniverse (SimulatedUniverse module):
            SimulatedUniverse class object
        Observatory (Observatory module):
            Observatory class object
        TimeKeeping (TimeKeeping module):
            TimeKeeping class object
        nt_flux (integer):
            Observation time sampling, to determine the integration time interval
        fullSpectra (boolean ndarray):
            Indicates if planet spectra have been captured
        partialSpectra (boolean ndarray):
            Indicates if planet partial spectra have been captured
        starVisits (integer ndarray):
            Contains the number of times each target was visited
        starTimes (astropy Quantity array):
            Contains the last time the star was observed in units of day
        starRevisit (float nx2 ndarray):
            Contains indices of targets to revisit and revisit times 
            of these targets in units of day
        starExtended (integer ndarray):
            Contains indices of targets with detected planets, updated throughout 
            the mission
        lastDetected (float nx4 ndarray):
            For each target, contains 4 lists with planets' detected status, exozodi 
            brightness (in 1/arsec2), delta magnitude, and working angles (in mas)
        DRM (list of dicts):
            Contains the results of survey simulation
        
    """

    _modtype = 'SurveySimulation'
    _outspec = {}

    def __init__(self, nt_flux=1, logLevel='ERROR', scriptfile=None, **specs):
        """Initializes Survey Simulation with default values
        
        Input: 
            nt_flux (integer):
                Observation time sampling, to determine the integration time interval
            logLevel (string):
                Defines a logging level for the logger handler. Valid levels are: INFO, 
                CRITICAL, ERROR, WARNING, DEBUG (case is ignored). Defaults to 'INFO'.
            scriptfile (string):
                JSON script file.  If not set, assumes that 
                dictionary has been passed through specs 
                
        """
        
        # toggle the logging level: INFO, DEBUG, WARNING, ERROR, CRITICAL
        if logLevel.upper() == 'INFO':
            logging.basicConfig(level=logging.INFO)
        elif logLevel.upper() == 'DEBUG':
            logging.basicConfig(level=logging.DEBUG)
        elif logLevel.upper() == 'WARNING':
            logging.basicConfig(level=logging.WARNING)
        elif logLevel.upper() == 'ERROR':
            logging.basicConfig(level=logging.ERROR)
        elif logLevel.upper() == 'CRITICAL':
            logging.basicConfig(level=logging.CRITICAL)
        
        # if a script file is provided read it in
        if scriptfile is not None:
            import json
            import os.path
            assert os.path.isfile(scriptfile), "%s is not a file."%scriptfile
            
            try:
                script = open(scriptfile).read()
                specs = json.loads(script)
            except ValueError:
                sys.stderr.write("Error.  Script file `%s' is not valid JSON." % scriptfile)
                # must re-raise, or the error will be masked 
                raise
            except:
                sys.stderr.write("Unexpected error while reading specs file: " + sys.exc_info()[0])
                raise
            
            # modules array must be present
            if 'modules' not in specs.keys():
                raise ValueError("No modules field found in script.")
        
        #if any of the modules is a string, assume that they are all strings and we need to initalize
        if isinstance(specs['modules'].itervalues().next(),basestring):
            
            # import desired module names (prototype or specific)
            self.SimulatedUniverse = get_module(specs['modules'] \
                    ['SimulatedUniverse'],'SimulatedUniverse')(**specs)
            self.Observatory = get_module(specs['modules'] \
                    ['Observatory'],'Observatory')(**specs)
            self.TimeKeeping = get_module(specs['modules'] \
                    ['TimeKeeping'],'TimeKeeping')(**specs)
            
            # bring inherited class objects to top level of Survey Simulation
            SU = self.SimulatedUniverse
            self.PlanetPopulation = SU.PlanetPopulation
            self.PlanetPhysicalModel = SU.PlanetPhysicalModel
            self.OpticalSystem = SU.OpticalSystem
            self.ZodiacalLight = SU.ZodiacalLight
            self.BackgroundSources = SU.BackgroundSources
            self.PostProcessing = SU.PostProcessing
            self.Completeness = SU.Completeness
            self.TargetList = SU.TargetList
        else:
            #these are the modules that must be present if passing instantiated objects
            neededObjMods = ['PlanetPopulation',
                          'PlanetPhysicalModel',
                          'OpticalSystem',
                          'ZodiacalLight',
                          'BackgroundSources',
                          'PostProcessing',
                          'Completeness',
                          'TargetList',
                          'SimulatedUniverse',
                          'Observatory',
                          'TimeKeeping']
            
            #ensure that you have the minimal set
            for modName in neededObjMods:
                if modName not in specs['modules'].keys():
                    raise ValueError("%s module is required but was not provided." % modName)
            
            for modName in specs['modules'].keys():
                assert (specs['modules'][modName]._modtype == modName), \
                "Provided instance of %s has incorrect modtype."%modName
                
                setattr(self, modName, specs['modules'][modName])
        
        # observation time sampling (must be an integer)
        self.nt_flux = int(nt_flux)
        # list of simulation results, each item is a dictionary
        self.DRM = []

    def __str__(self):
        """String representation of the Survey Simulation object
        
        When the command 'print' is used on the Survey Simulation object, this 
        method will return the values contained in the object"""
        
        for att in self.__dict__.keys():
            print '%s: %r' % (att, getattr(self, att))
        
        return 'Survey Simulation class object attributes'

    def run_sim(self):
        """Performs the survey simulation 
        
        Returns:
            mission_end (string):
                Messaged printed at the end of a survey simulation.
        
        """
        
        OS = self.OpticalSystem
        TL = self.TargetList
        SU = self.SimulatedUniverse
        Obs = self.Observatory
        TK = self.TimeKeeping
        
        Logger.info('run_sim beginning')
        
        # initialize lists updated later
        self.fullSpectra = np.zeros(SU.nPlans, dtype=int)
        self.partialSpectra = np.zeros(SU.nPlans, dtype=int)
        self.starVisits = np.zeros(TL.nStars,dtype=int)
        self.starTimes = np.zeros(TL.nStars)*u.d
        self.starRevisit = np.array([])
        self.starExtended = np.array([])
        self.lastDetected = np.empty((TL.nStars, 4), dtype=object)
        
        # TODO: start using this self.currentSep
        # set occulter separation if haveOcculter
        if OS.haveOcculter == True:
            self.currentSep = Obs.occulterSep
        
        # Choose observing modes selected for detection (default marked with a flag),
        detMode = filter(lambda mode: mode['detectionMode'] == True, OS.observingModes)[0]
        # and for characterization (default is first spectro/IFS mode)
        spectroModes = filter(lambda mode: 'spec' in mode['inst']['name'], OS.observingModes)
        if np.any(spectroModes):
            charMode = spectroModes[0]
        # if no spectro mode, default char mode is first observing mode
        else:
            charMode = OS.observingModes[0]
        
        # loop until mission is finished
        sInd = None
        while not TK.mission_is_over():
            
            # Acquire the NEXT TARGET star index:
            sInd, t_det, slewTime = self.next_target(sInd, detMode)
            
            if sInd is not None:
                # get the index of the selected target for the extended list
                if TK.currentTimeNorm > TK.missionLife and self.starExtended.shape[0] == 0:
                    for i in range(len(self.DRM)):
                        if np.any([x == 1 for x in self.DRM[i]['plan_detected']]):
                            self.starExtended = np.hstack((self.starExtended, self.DRM[i]['star_ind']))
                            self.starExtended = np.unique(self.starExtended)
                
                # Beginning of observation, create DRM and start to populate it
                obsBegin = TK.currentTimeNorm.to('day')
                Logger.info('current time is %r' % obsBegin)
                print 'Current mission time: ', obsBegin
                DRM = {}
                DRM['star_ind'] = sInd
                DRM['arrival_time'] = TK.currentTimeNorm.to('day').value
                pInds = np.where(SU.plan2star == sInd)[0]
                DRM['plan_inds'] = pInds.astype(int).tolist()
                
                # PERFORM DETECTION and populate revisit list attribute
                detBegin = TK.currentTimeNorm.to('day')
                detected, detSNR, FA = self.observation_detection(sInd, t_det, detMode)
                DRM['int_time_det'] = t_det.to('day').value
                DRM['plan_detected'] = detected.tolist()
                DRM['plan_det_fEZ'] = SU.fEZ[pInds].to('1/arcsec2').value.tolist()
                DRM['plan_det_dMag'] = SU.dMag[pInds].tolist()
                DRM['plan_det_WA'] = SU.WA[pInds].to('mas').value.tolist()
                DRM['SNR_det'] = detSNR.tolist()
                # false alarm delta magnitude and working angle
                if FA == True:
                    DRM['FA_fEZ'] = self.lastDetected[sInd,1][-1]
                    DRM['FA_dMag'] = self.lastDetected[sInd,2][-1]
                    DRM['FA_WA'] = self.lastDetected[sInd,3][-1]
                
                # PERFORM CHARACTERIZATION and populate spectra list attribute
                charBegin = TK.currentTimeNorm.to('day')
                characterized, charSNR, t_char = self.observation_characterization(sInd, charMode)
                DRM['int_time_char'] = t_char.to('day').value
                DRM['plan_characterized'] = characterized.tolist()
                DRM['plan_char_fEZ'] = SU.fEZ[pInds].to('1/arcsec2').value.tolist()
                DRM['plan_char_dMag'] = SU.dMag[pInds].tolist()
                DRM['plan_char_WA'] = SU.WA[pInds].to('mas').value.tolist()
                DRM['SNR_char'] = charSNR.tolist()
                # store characterization mode in DRM, charModes must be a list of dictionaries
                DRM['charModes'] = [dict(charMode)]
                del DRM['charModes'][0]['inst'], DRM['charModes'][0]['syst']
                
                # Update the OCCULTER wet mass and store all occulter 
                # related values in the DRM
                if OS.haveOcculter == True:
                    DRM = self.update_occulter_mass(DRM, slewTime, t_det, t_char, \
                            detBegin, charBegin)
                
                # update target time
                self.starTimes[sInd] = TK.currentTimeNorm
                
                # append result values to self.DRM
                self.DRM.append(DRM)
                
                # with occulter, if spacecraft fuel is depleted, exit loop
                if OS.haveOcculter and Obs.scMass < Obs.dryMass:
                    print 'Total fuel mass exceeded at %r' % TK.currentTimeNorm
                    break
        
        mission_end = "Simulation finishing OK. Results stored in SurveySimulation.DRM"
        Logger.info(mission_end)
        print mission_end
        
        return mission_end

    def next_target(self, old_sInd, mode):
        """Finds index of next target star and calculates its integration time.
        
        This method chooses the next target star index based on which
        stars are available, their integration time, and maximum completeness.
        Returns None if no target could be found.
        
        Args:
            old_sInd (integer):
                Index of the previous target star
            mode (dict):
                Selected observing mode for detection
                
        Returns:
            sInd (integer):
                Index of next target star. Defaults to None.
            t_det (astropy Quantity):
                Selected star integration time for detection in units of day. 
                Defaults to None.
            slewTime (astropy Quantity):
                Slew time to next target in units of day. Defaults to zero.
        
        """
        
        OS = self.OpticalSystem
        ZL = self.ZodiacalLight
        TL = self.TargetList
        Obs = self.Observatory
        TK = self.TimeKeeping
        
        # Allocate settling time + overhead time
        TK.allocate_time(Obs.settlingTime + mode['syst']['ohTime'])
        # In case of an occulter, initialize slew time factor
        # (add transit time and reduce starshade mass)
        if OS.haveOcculter == True:
            ao = Obs.thrust/Obs.scMass
            slewTime_fac = (2.*Obs.occulterSep/np.abs(ao)/(Obs.defburnPortion/2. \
                    - Obs.defburnPortion**2/4.)).decompose().to('d2')
        
        # Now, start to look for available targets
        while not TK.mission_is_over():
            # 0/ initialize arrays
            slewTime = np.zeros(TL.nStars)*u.d
            fZs = np.zeros(TL.nStars)/u.arcsec**2
            t_dets = np.zeros(TL.nStars)*u.d
            tovisit = np.zeros(TL.nStars, dtype=bool)
            sInds = np.array(range(TL.nStars))
            
            # 1/ find spacecraft orbital START positions and filter out unavailable 
            # targets. If occulter, each target has its own START position.
            if OS.haveOcculter == True:
                # find angle between old and new stars, default to pi/2 for first target
                if old_sInd is None:
                    sd = np.zeros(TL.nStars)*u.rad
                else:
                    # position vector of previous target star
                    r_old = Obs.starprop(TL, old_sInd, TK.currentTimeAbs)
                    u_old = r_old/np.sqrt(np.sum(r_old**2))
                    # position vector of new target stars
                    r_new = Obs.starprop(TL, sInds, TK.currentTimeAbs)
                    u_new = r_new/np.sqrt(np.sum(r_new**2))
                    # angle between old and new stars
                    sd = np.arccos(np.dot(u_old, u_new.T))[0]
                    sd[np.where(np.isnan(sd))] = 0.
                # calculate slew time
                slewTime = np.sqrt(slewTime_fac*np.sin(sd/2.))
            
            startTime = TK.currentTimeAbs + slewTime
            r_sc = Obs.orbit(startTime)
            kogoodStart = Obs.keepout(TL, sInds, startTime, r_sc, OS.telescopeKeepout)
            sInds = sInds[np.where(kogoodStart)[0]]
            
            # 2/ calculate integration times for the preselected targets, 
            # and filter out t_tot > integration cutoff
            if np.any(sInds):
                fZ = ZL.fZ(TL, sInds, mode['lam'], r_sc[sInds])
                fEZ = ZL.fEZ0
                t_dets[sInds] = OS.calc_maxintTime(TL, sInds, fZ, fEZ, mode)
                # include integration time multiplier
                t_tot = t_dets*mode['timeMultiplier']
                # total time must be positive and shorter than treshold
                sInds = np.where((0 < t_tot) & (t_tot < OS.intCutoff))[0]
            
            # 3/ find spacecraft orbital END positions (for each candidate target), 
            # and filter out unavailable targets
            if np.any(sInds):
                endTime = startTime[sInds] + t_dets[sInds]
                r_sc = Obs.orbit(endTime)
                kogoodEnd = Obs.keepout(TL, sInds, endTime, r_sc, OS.telescopeKeepout)
                sInds = sInds[np.where(kogoodEnd)[0]]
            
            # 4/ filter out all previously (more-)visited targets, unless in 
            # revisit list, with time within some dt of start (+- 1 week)
            if np.any(sInds):
                tovisit[sInds] = (self.starVisits[sInds] == self.starVisits[sInds].min())
                if self.starRevisit.size != 0:
                    dt_max = 1.*u.week
                    dt_rev = np.abs(self.starRevisit[:,1]*u.day - TK.currentTimeNorm)
                    ind_rev = [int(x) for x in self.starRevisit[dt_rev < dt_max,0] if x in sInds]
                    tovisit[ind_rev] = True
                sInds = np.where(tovisit)[0]
            
            # 5/ choose best target from remaining
            if np.any(sInds):
                # prototype version choose sInd among targets with highest completeness
                comp = TL.comp0[sInds]
                inds = np.where((self.starVisits > 0)[sInds])[0]
                comp[inds] =  self.Completeness.completeness_update(TL, sInds[inds], TK.currentTimeNorm) ####CHECK ME
                mask = np.where(comp == max(comp))[0]
                sInd = np.random.choice(sInds[mask])
                # update visited list for current star
                self.starVisits[sInd] += 1
                # store relevant values
                t_det = t_dets[sInd]
                break
            
            # if no observable target, allocate time and try again
            # TODO: improve how to deal with no available target
            else:
                TK.allocate_time(TK.dtAlloc)
            
        else:
            Logger.info('Mission complete: no more time available')
            return None, None, None
        
        if OS.haveOcculter == True:
            # update current time by adding slew time for the chosen target
            TK.allocate_time(slewTime[sInd])
            if TK.mission_is_over():
                Logger.info('Mission complete: no more time available')
                return None, None, None
        
        return sInd, t_det, slewTime[sInd]

    def observation_detection(self, sInd, t_det, mode):
        """Determines the detection status, and updates the last detected list 
        and the revisit list. 
        
        This method encodes detection status values in the DRM 
        dictionary.
        
        Args:
            sInd (integer):
                Integer index of the star of interest
            t_det (astropy Quantity):
                Selected star integration time for detection in units of day. 
                Defaults to None.
            mode (dict):
                Selected observing mode for detection
        
        Returns:
            detected (integer ndarray):
                Detection status for each planet orbiting the observed target star,
                where 1 is detection, 0 missed detection, -1 below IWA, and -2 beyond OWA
            SNR (float ndarray):
                Signal-to-noise ratio of the target's planets during detection
            FA (boolean):
                False alarm (false positive) boolean
        
        """
        
        PPop = self.PlanetPopulation
        OS = self.OpticalSystem
        ZL = self.ZodiacalLight
        PPro = self.PostProcessing
        TL = self.TargetList
        SU = self.SimulatedUniverse
        TK = self.TimeKeeping
        
        # Find indices of planets around the target
        pInds = np.where(SU.plan2star == sInd)[0]
        # Find cases with working angles (WA) out of IWA-OWA range
        observable = np.ones(len(pInds), dtype=int)
        if np.any(observable):
            WA = SU.WA[pInds]
            observable[WA < OS.IWA] = -1
            observable[WA > OS.OWA] = -2
        
        # Now, calculate SNR for any observable planet (within IWA-OWA range)
        obs = (observable == 1)
        if np.any(obs):
            # initialize Signal and Noise arrays
            Signal = np.zeros((self.nt_flux, len(pInds[obs])))
            Noise = np.zeros((self.nt_flux, len(pInds[obs])))
            # integrate the signal (planet flux) and noise
            dt = t_det/self.nt_flux
            for i in range(self.nt_flux):
                s,n = self.calc_signal_noise(sInd, pInds[obs], dt, mode)
                Signal[i,:] = s
                Noise[i,:] = n
            # calculate SNR
            SNR = Signal.sum(0) / Noise.sum(0)
            # allocate extra time for timeMultiplier
            t_extra = t_det*(mode['timeMultiplier'] - 1)
            TK.allocate_time(t_extra)
        # if no planet, just observe for t_tot (including time multiplier)
        else:
            SNR = np.array([])
            t_tot = t_det*(mode['timeMultiplier'])
            TK.allocate_time(t_tot)
        
        # Find out if a false positive (false alarm) or any false negative 
        # (missed detections) have occurred, and populate detection status array
        FA, MD = PPro.det_occur(SNR)
        detected = observable
        if np.any(obs):
            detected[obs] = (~MD).astype(int)
        
        # If planets are detected, calculate the minimum apparent separation
        smin = None
        det = (detected == 1)
        if np.any(det):
            smin = np.min(SU.s[pInds[det]])
            Logger.info('Detected planet(s) %r of target %r' % (pInds[det], sInd))
            print 'Detected planet(s)', pInds[det], 'of target', sInd
        
        # Populate the lastDetected array by storing det, fEZ, dMag, and WA
        self.lastDetected[sInd,:] = det, SU.fEZ[pInds].to('1/arcsec2').value, \
                    SU.dMag[pInds], SU.WA[pInds].to('mas').value
        
        # In case of a FA, generate a random delta mag (between maxFAfluxratio and
        # dMagLim) and working angle (between IWA and min(OWA, a_max))
        if FA == True:
            WA = np.random.uniform(OS.IWA.to('mas'), np.minimum(OS.OWA, \
                    np.arctan(max(PPop.arange)/TL.dist[sInd])).to('mas'))
            dMag = np.random.uniform(-2.5*np.log10(PPro.maxFAfluxratio(WA*u.mas)), OS.dMagLim)
            fEZ = ZL.fEZ0.to('1/arcsec2').value
            self.lastDetected[sInd,0] = np.append(self.lastDetected[sInd,0], True)
            self.lastDetected[sInd,1] = np.append(self.lastDetected[sInd,1], fEZ)
            self.lastDetected[sInd,2] = np.append(self.lastDetected[sInd,2], dMag)
            self.lastDetected[sInd,3] = np.append(self.lastDetected[sInd,3], WA)
            sminFA = np.tan(WA)*TL.dist[sInd].to('AU')
            smin = np.minimum(smin,sminFA) if smin is not None else sminFA
            Logger.info('False Alarm at target %r with WA %r and dMag %r' % (sInd, WA, dMag))
            print 'False Alarm at target', sInd, 'with WA', WA, 'and dMag', dMag
        
        # In both cases (detection or false alarm), schedule a revisit 
        # based on minimum separation
        Ms = TL.MsTrue[sInd]*const.M_sun
        if smin is not None:
            sp = smin
            pInd_smin = pInds[det][np.argmin(SU.s[pInds[det]])]
            Mp = SU.Mp[pInd_smin]
            mu = const.G*(Mp + Ms)
            T = 2.*np.pi*np.sqrt(sp**3/mu)
            t_rev = TK.currentTimeNorm + T/2.
        # Otherwise, revisit based on average of population semi-major axis and mass
        else:
            sp = SU.s.mean()
            Mp = SU.Mp.mean()
            mu = const.G*(Mp + Ms)
            T = 2.*np.pi*np.sqrt(sp**3/mu)
            t_rev = TK.currentTimeNorm + 0.75*T
        
        # Finally, populate the revisit list (NOTE: sInd becomes a float)
        revisit = np.array([sInd, t_rev.to('day').value])
        if self.starRevisit.size == 0:
            self.starRevisit = np.array([revisit])
        else:
            self.starRevisit = np.vstack((self.starRevisit, revisit))
        
        return detected, SNR, FA

    def observation_characterization(self, sInd, mode):
        """Finds if characterizations are possible and relevant information
        
        Args:
            sInd (integer):
                Integer index of the star of interest
            mode (dict):
                Selected observing mode for characterization
        
        Returns:
            characterized (integer ndarray):
                Characterization status for each planet orbiting the observed target
                star, where 1 is full spectrum, 0 no spectrum, -1 partial spectrum
            SNR (float ndarray):
                Signal-to-noise ratio of the characterized planets. Defaults to None.
            t_char (astropy Quantity):
                Selected star characterization time in units of day. Defaults to None.
        
        """
        
        OS = self.OpticalSystem
        ZL = self.ZodiacalLight
        TL = self.TargetList
        SU = self.SimulatedUniverse
        Obs = self.Observatory
        TK = self.TimeKeeping
        
        # Find indices of planets around the target
        pInds = np.where(SU.plan2star == sInd)[0]
        # Get the last detected planets, and check if there was a FA
        det = self.lastDetected[sInd,0]
        FA = (det.size == pInds.size+1)
        if FA == True:
            pInds = np.append(pInds,-1)
        
        # Initialize outputs, and check if any planet to characterize
        characterized = np.zeros(det.size)
        SNR = np.array([])
        t_char = 0*u.d
        if not np.any(pInds):
            return characterized, SNR, t_char
        
        # Look for last detected planets that have not been fully characterized
        pIndsDet = pInds[det]
        if (FA == False):
            tochar = (self.fullSpectra[pIndsDet] != 1)
        elif pIndsDet.size > 1:
            tochar = (self.fullSpectra[pIndsDet[:-1]] != 1)
            tochar = np.append(tochar,True)
        else:
            tochar = np.array([True])
        
        # Also, find spacecraft orbital START position and check keepout angle
        startTime = TK.currentTimeAbs
        r_sc = Obs.orbit(startTime)
        kogoodStart = Obs.keepout(TL, sInd, startTime, r_sc, OS.telescopeKeepout)
        
        # If kogood, and any planet to characterize, find the characterization times
        if kogoodStart and np.any(tochar):
            # Propagate the whole system to match up with current time
            SU.propag_system(sInd, TK.currentTimeNorm)
            # Calculate characterization times
            fZ = ZL.fZ(TL, sInd, mode['lam'], r_sc)
            dMag = self.lastDetected[sInd,1][det][tochar]
            WA = self.lastDetected[sInd,2][det][tochar]
            t_chars = OS.calc_intTime(TL, sInd, fZ, ZL.fEZ0, dMag, WA, mode)
            t_tots = t_chars*(mode['timeMultiplier'])
            # Filter out planets with t_tots > integration cutoff
            cutoff = np.where(t_tots < OS.intCutoff)[0]
            # Is target still observable at the end of any char time?
            endTime = TK.currentTimeAbs + t_tots[cutoff]
            r_sc = Obs.orbit(endTime)
            kogoodEnd = Obs.keepout(TL, sInd, endTime, r_sc, OS.telescopeKeepout)
            # If yes, perform the characterization for the maximum char time
            if np.any(kogoodEnd):
                t_char = np.max(t_chars[cutoff][kogoodEnd])
                pIndsChar = pIndsDet[tochar][cutoff][kogoodEnd]
                Logger.info('Characterized planet(s) %r of target %r' % (pIndsChar, sInd))
                print 'Characterized planet(s)', pIndsChar, 'of target', sInd
                
                # SNR CALCULATION:
                # First, calculate SNR for planets to characterize (without false alarm)
                planinds = pIndsChar[:-1] if pIndsChar[-1] == -1 else pIndsChar
                # initialize Signal and Noise arrays
                Signal = np.zeros((self.nt_flux, len(planinds)))
                Noise = np.zeros((self.nt_flux, len(planinds)))
                # integrate the signal (planet flux) and noise
                dt = t_char/self.nt_flux
                for i in range(self.nt_flux):
                    s,n = self.calc_signal_noise(sInd, planinds, dt, mode)
                    Signal[i,:] = s
                    Noise[i,:] = n
                # calculate SNR
                SNR = Signal.sum(0) / Noise.sum(0)
                # allocate extra time for timeMultiplier
                t_extra = t_char*(mode['timeMultiplier'] - 1)
                TK.allocate_time(t_extra)
                # Then, calculate the false alarm SNR (if characterized)
                SNR_FA = np.array([])
                if pIndsChar[-1] == -1:
                    fEZ = self.lastDetected[sInd,1][-1]/u.arcsec**2
                    dMag = self.lastDetected[sInd,2][-1]
                    WA = self.lastDetected[sInd,3][-1]*u.mas
                    C_p, C_b, C_sp = OS.Cp_Cb_Csp(TL, sInd, fZ, fEZ, dMag, WA, mode)
                    SNR_FA = (C_p*t_char/np.sqrt(C_b*t_char + (C_sp*t_char)**2))\
                            .decompose().value
                # Finally, merge SNRs from planet and FA into one array
                SNR = np.append(SNR, SNR_FA)
                
                # Now, store characterization status: 0 for not characterized,
                # -1 for partially characterized, 1 for fully characterized planets.
                if np.any(SNR):
                    char = (SNR > mode['SNR'])
                    if np.any(char):
                        # initialize with partial spectra
                        characterized[det][tochar][cutoff][kogoodEnd][char] = -1
                        # check for full spectra
                        WA = self.lastDetected[sInd,3]*u.mas
                        WAchar = WA[det][tochar][cutoff][kogoodEnd][char]
                        IWA_max = OS.IWA*(1+mode['BW']/2.)
                        OWA_min = OS.OWA*(1-mode['BW']/2.)
                        full = np.where((WAchar > IWA_max) & (WAchar < OWA_min))[0]
                        characterized[det][tochar][cutoff][kogoodEnd][char][full] = 1
                        # encode results in spectra lists
                        partial = pInds[np.where(characterized == -1)[0]]
                        if np.any(partial):
                            partial = partial[:-1] if partial[-1] == -1 else partial
                            self.partialSpectra[partial] += 1
                        full = pInds[np.where(characterized == 1)[0]]
                        if np.any(full):
                            full = full[:-1] if full[-1] == -1 else full
                            self.fullSpectra[full] += 1
        
        return characterized, SNR, t_char

    def calc_signal_noise(self, sInd, pInds, t_int, mode):
        """Calculates the signal and noise fluxes for a given time interval. Called
        by observation_detection and observation_characterization methods in the 
        SurveySimulation module.
        
        Args:
            sInd (integer):
                Integer index of the star of interest
            pInds (integer):
                Integer indices of the planets of interest
            t_int (astropy Quantity):
                Integration time interval in units of day
            mode (dict):
                Selected observing mode (from OpticalSystem)
        
        Returns:
            Signal (float)
                Counts of signal
            Noise (float)
                Counts of background noise variance
        """
        
        OS = self.OpticalSystem
        ZL = self.ZodiacalLight
        TL = self.TargetList
        SU = self.SimulatedUniverse
        Obs = self.Observatory
        TK = self.TimeKeeping
        
        # allocate first half of t_int
        TK.allocate_time(t_int/2.)
        # propagate the system to match up with current time
        SU.propag_system(sInd, TK.currentTimeNorm)
        # find spacecraft position and ZodiacalLight
        r_sc = Obs.orbit(TK.currentTimeAbs)
        fZ = ZL.fZ(TL, sInd, mode['lam'], r_sc)
        # find electron counts for planet, background, and speckle residual 
        C_p, C_b, C_sp = OS.Cp_Cb_Csp(TL, sInd, fZ, \
                SU.fEZ[pInds], SU.dMag[pInds], SU.WA[pInds], mode)
        # calculate signal and noise levels (based on Nemati14 formula)
        Signal = (C_p*t_int).decompose().value
        Noise = np.sqrt((C_b*t_int + (C_sp*t_int)**2).decompose().value)
        # allocate second half of t_int
        TK.allocate_time(t_int/2.)
        
        return Signal, Noise

    def update_occulter_mass(self, DRM, slewTime, t_det, t_char, detBegin, charBegin):
        """Updates the occulter wet mass in the Observatory module, and stores all 
        the occulter related values in the DRM array.
        
        Args:
            DRM (dicts):
                Contains the results of survey simulation
            slewTime (astropy Quantity):
                Slew time to next target in units of day
            t_det (astropy Quantity):
                Selected star integration time for detection in units of day
            t_char (astropy Quantity):
                Selected star integration time for characterization in units of day
            detBegin (astropy Time):
                Absolute time of the beginning of detection in MJD
            charBegin (astropy Time):
                Absolute time of the beginning of characterization in MJD
                
        Returns:
            DRM (dicts):
                Contains the results of survey simulation
        
        """
        
        TL = self.TargetList
        Obs = self.Observatory
        
        # find values related to slew time
        DRM['slew_time'] = slewTime.to('day').value
        ao = Obs.thrust/Obs.scMass
        slewTime_fac = (2.*Obs.occulterSep/np.abs(ao)/(Obs.defburnPortion/2. \
                - Obs.defburnPortion**2/4.)).decompose().to('d2')
        sd = 2.*np.arcsin(slewTime**2/slewTime_fac)
        DRM['slew_angle'] = sd.to('deg').value
        slew_mass_used = slewTime*Obs.defburnPortion*Obs.flowRate
        DRM['slew_dV'] = (slewTime*ao*Obs.defburnPortion).to('m/s').value
        DRM['slew_mass_used'] = slew_mass_used.to('kg').value
        
        # DETECTION
        # find disturbance forces on occulter
        dF_lateral, dF_axial = Obs.distForces(TL, sInd, detBegin)
        # decrement mass for station-keeping
        _, det_mass_used, det_deltaV = Obs.mass_dec(dF_lateral, t_det)
        DRM['det_dV'] = det_deltaV.to('m/s').value
        DRM['det_mass_used'] = det_mass_used.to('kg').value
        # update spacecraft mass
        Obs.scMass -= (slew_mass_used + det_mass_used)
        DRM['det_scMass'] = Obs.scMass.to('kg').value
        
        # CHARACTERIZATION
        # find disturbance forces on occulter
        dF_lateral, dF_axial = Obs.distForces(TL, sInd, charBegin)
        # decrement mass for station-keeping
        intMdot, _, _ = Obs.mass_dec(dF_lateral, t_char)
        char_deltaV = dF_lateral/Obs.scMass*t_char
        char_mass_used = intMdot*t_char
        DRM['char_dV'] = char_deltaV.to('m/s').value
        DRM['char_mass_used'] = char_mass_used.to('kg').value
        # update spacecraft mass
        Obs.scMass -= mass_used_char
        DRM['char_scMass'] = Obs.scMass.to('kg').value
        
        return DRM
