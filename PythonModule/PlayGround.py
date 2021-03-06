import time
from scipy.fft import fft, fftfreq, fftshift, ifft
import scipy.signal as signal

import numpy as np
import array

from matplotlib import pyplot

from scpi.lp_socket import *
from IQsamplesIO import *

from sUtility import *
from DMRSgeneration import *
import NRparameters


if __name__ == "__main__":


    if True:
        logger.logLevel = 4
        logger.enablePrint = True
        logger.start()
        lp = connect_tester("10.201.13.138")
        interface = IO(lp,logger)
        lp.exec("CHAN1;VSA11;INIT;")
        lp.query("*WAI;ERR:ALL?")
        IQsample = interface.readIQsample(1)
        data = np.array(IQsample[1]) + 1j*np.array(IQsample[2])
        logger.stop()
    else:
        #-----------------------------------------------------------------
        # load data
        #filename = "qcom_mu3_bw100_66@0.dat"
        filename = "0.dat"
        #filename = "mu3_bw100_qpsk_tfpc0_rbo000_rbd066.dat"

        f = open(filename, 'rb')
        packData = f.read()
        f.close()
        IQsample = np.array(array.array('f',packData))
        data = IQsample[0::2] + 1j* IQsample[1::2]
        #-----------------------------------------------------------------

    

    #-------------------------------------------------------------------
    # parameters
    # FR2 example
    class para:
        dmrsSymb = 3
        numerology = 3
        rbNum = 66
        FFTsizeExp = 10
        waveformSamplingRate = 2457600000
        scs = (1<<numerology) * 15000
        expectedSamplingRate = scs << FFTsizeExp
        samplingRateRatio = waveformSamplingRate/expectedSamplingRate
    # FR1 example
    class para:
        dmrsSymb = 3
        numerology = 1
        rbNum = 273
        FFTsizeExp = 12
        waveformSamplingRate = 240000000
        scs = (1<<numerology) * 15000
        expectedSamplingRate = scs << FFTsizeExp
        samplingRateRatio = waveformSamplingRate/expectedSamplingRate

    #-------------------------------------------------------------------
    # IQdata info and re-sample

    numSamples = np.size(data)

    print("Capture Length: " + str(numSamples/240))
    print("Number of samples: " + str(numSamples))

    print("Ratio: " + str(para.samplingRateRatio))
    print("Sampling Rate: " + str(int(para.expectedSamplingRate)))
    data = signal.resample(data, int(numSamples/para.samplingRateRatio))
    print("Number of samples: " + str(np.size(data)))

    #-------------------------------------------------------------------
    # CP self correlation

    p = NRparameters.unit(para.numerology,para.expectedSamplingRate)

    start = time.time()
    c = np.absolute(self_correlate(data, p.normal_cp_sample, p.symbol_sample, True))
    print("self_correlation time: " + str(time.time()-start))

    handle1 = pyplot.figure()
    pyplot.plot(c)

    #---------------------------------------------------------------------
    # frequency offset estimation, resolution (-pi,pi)
    
    cp_start = np.argmax(c[0:4096])
    phase_shift = np.multiply( data[cp_start:cp_start+p.normal_cp_sample], np.conj(data[cp_start + p.symbol_sample:cp_start+p.symbol_sample+p.normal_cp_sample]))
    phase_shift_ave = np.average(phase_shift)
    freqOffset = np.angle(phase_shift_ave)/4096

    print("Estimated frequency offset: " + str(freqOffset/2/np.pi*para.expectedSamplingRate) + "Hz")

    #---------------------------------------------------------------------
    # frequency offset compensation

    freqComp = np.sin(freqOffset*np.array(range(np.size(data)))) - 1j* np.sin(np.pi/2 + freqOffset*np.array(range(np.size(data))))
    data = np.multiply(data,freqComp)

    phase_shift = np.multiply( data[cp_start:cp_start+p.normal_cp_sample], np.conj(data[cp_start + p.symbol_sample:cp_start+p.symbol_sample+p.normal_cp_sample]))
    phase_shift_ave = np.average(phase_shift)
    freqOffset = np.angle(phase_shift_ave)/4096

    print("Frequency offset adjust: " + str(freqOffset/np.pi*para.expectedSamplingRate) + "Hz")

    #---------------------------------------------------------------------
    # uplink DMRS correlation

    a = UL_DMRS()
    a.transformPrecoding = False
    a.N_Id_n_SCID = 0

    result = []

    cFloor = []
    cRoof = []

    for i in range(20):

        #RE value should be always generated with max number RB 
        RE = a.REvalue(12*273,i,para.dmrsSymb)

        reArrange = a.fillShift(RE,1<<para.FFTsizeExp,273,para.rbNum,0)

        data  = (data - np.mean(data))/ np.std(data)
        refSignal = ifft(reArrange)
        
        c = np.absolute(signal.correlate(data,refSignal,mode = 'valid'))/30

        result.append(np.max(c))
        if np.max(c) > 0.7:
            cRoof.append(np.max(c))
            pyplot.plot(c[::])
        else:
            cFloor.append(np.max(c))

        print(str(i) + " : " +  str(np.max(c)))

        start = np.argmax(c) - int(len(refSignal)/2)
        end = start + len(refSignal)
        refPart = data[start:end:]
    
    
    handle1.show()
    input()

    



