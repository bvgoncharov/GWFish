#!/usr/bin/env python

import numpy as np
import pandas as pd

from numpy.random import default_rng

import time
import json

from itertools import combinations, chain

from tqdm import tqdm

import argparse

import GWFish.modules as gw

rng = default_rng()

def powerset(length):
    it = chain.from_iterable((combinations(range(length), r)) for r in range(length+1))
    return list(it)[1:]

def main():
    # example to run with command-line arguments:
    # python CBC_Simulation.py --pop_file=CBC_pop.hdf5 --detectors ET CE2 --networks [[0,1],[0],[1]]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--pop_file', type=str, default='./injections/CBC_pop.hdf5',
        help='Population to run the analysis on.'
             'Runs on BBH_1e5.hdf5 if no argument given.')
    parser.add_argument(
        '--pop_id', type=str, default='BBH',
        help='Short population identifier for file names. Uses BBH if no argument given.')
    parser.add_argument(
        '--detectors', type=str, default=['ET'], nargs='+',
        help='Detectors to analyze. Uses ET as default if no argument given.')
    parser.add_argument(
        '--networks', default='[[0]]',
        help='''Network IDs: list of lists of detector IDs. 
Uses [[0]] (only the first detector) as default if no argument given.
Use "all" to get all possible combinations of the detectors given.''')
    parser.add_argument(
        '--config', type=str, default='GWFish/detectors.yaml',
        help='Configuration file where the detector specifications are stored. Uses GWFish/detectors.yaml as default if no argument given.')
    

    args = parser.parse_args()
    ConfigDet = args.config

    threshold_SNR = np.array([0., 9.])  # [min. individual SNR to be included in PE, min. network SNR for detection]
    calculate_errors = True   # whether to calculate Fisher-matrix based PE errors
    duty_cycle = False  # whether to consider the duty cycle of detectors

    #fisher_parameters = ['ra', 'dec', 'psi', 'theta_jn', 'luminosity_distance', 'mass_1', 'mass_2', 'geocent_time', 'phase']
    fisher_parameters = ['ra', 'dec', 'psi', 'theta_jn', 'luminosity_distance', 'mass_1', 'mass_2']
    #fisher_parameters = ['luminosity_distance','ra','dec']

    pop_file = args.pop_file
    population = args.pop_id

    detectors_ids = args.detectors
    
    if args.networks == 'all':
        networks_ids = powerset(len(detectors_ids))
    else:
        networks_ids = json.loads(args.networks)

    parameters = pd.read_hdf(pop_file)

    network = gw.detection.Network(detectors_ids, detection_SNR=threshold_SNR, parameters=parameters,
                                   fisher_parameters=fisher_parameters, config=ConfigDet)

    # lisaGWresponse(network.detectors[0], frequencyvector)
    # exit()

    # horizon(network, parameters.iloc[0], frequencyvector, threshold_SNR, 1./df, fmax)
    # exit()

    #waveform_model = 'TaylorF2'
    # waveform_model = 'IMRPhenomD'
    waveform_model = 'IMRPhenomXPHM'

    #waveform_class = gw.waveforms.IMRPhenomD
    waveform_class = gw.waveforms.LALFD_Waveform

    np.random.seed(0)
    
    print('Processing CBC population')
    for k in tqdm(np.arange(len(parameters))):
        parameter_values = parameters.iloc[k]

        networkSNR_sq = 0
        for d in np.arange(len(network.detectors)):
            data_params = {
                'frequencyvector': network.detectors[d].frequencyvector,
                'f_ref': 50.
            }
            waveform_obj = waveform_class(waveform_model, parameter_values, data_params)
            wave = waveform_obj()
            t_of_f = waveform_obj.t_of_f

            signal = gw.detection.projection(parameter_values, network.detectors[d], wave, t_of_f)

            SNRs = gw.detection.SNR(network.detectors[d], signal, duty_cycle=duty_cycle)
            networkSNR_sq += np.sum(SNRs ** 2)
            network.detectors[d].SNR[k] = np.sqrt(np.sum(SNRs ** 2))

            if calculate_errors:
                network.detectors[d].fisher_matrix[k, :, :] = \
                    gw.fishermatrix.FisherMatrix(waveform_obj, parameter_values, fisher_parameters, network.detectors[d]).fm

        network.SNR[k] = np.sqrt(networkSNR_sq)

    gw.detection.analyzeDetections(network, parameters, population, networks_ids)

    if calculate_errors:
        gw.fishermatrix.analyzeFisherErrors(network, parameters, fisher_parameters, population, networks_ids)

if __name__ == '__main__':
    start_time = time.time()
    main()
    print("--- %s seconds ---" % (time.time() - start_time))
