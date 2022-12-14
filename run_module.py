import csv
import os
import sys
import pickle

import result

sys.path.append(os.getcwd())
import numpy as np
import time
import multiprocessing

from timeit import default_timer as timer
from protocol_configs import IndicesToEncodeStrategy, CodeGenerationStrategy
from protocol_configs import ProtocolConfigs
from key_generator import KeyGenerator
from multi_block_protocol import MultiBlockProtocol
from result import Result
import math


def write_header(file_name):
    try:
        with open(file_name, 'r') as f:
            for row in f:
                assert(row.rstrip('\n').split(",") == result.get_header())
                return
    except FileNotFoundError:
        with open(file_name, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(result.get_header())
    except AssertionError:
        raise AssertionError(f"Header of {file_name} is bad.")

def write_results(result_list, verbosity=False):
    if verbosity:
        print("writing results")
    raw_results_file_name = result_list[0].cfg.raw_results_file_path
    with open(raw_results_file_name, 'a', newline='') as f1:
        writer = csv.writer(f1)
        for single_result in result_list:
            writer.writerow(single_result.get_row())

    agg_results_file_name = result_list[0].cfg.agg_results_file_path
    with open(agg_results_file_name, 'a', newline='') as f2:
        writer = csv.writer(f2)
        writer.writerow(Result(result_list[0].cfg, result_list=result_list).get_row())

def single_run(cfg):
    # print(f"I'm process {os.getpid()}")
    np.random.seed([os.getppid(), int(str(time.time() % 1)[2:10])])
    key_generator = KeyGenerator(p_err=cfg.p_err, key_length=cfg.key_length, base=cfg.base)
    a, b = key_generator.generate_keys()
    protocol = MultiBlockProtocol(cfg, a, b)
    return protocol.run()

def multi_run_series(cfg, sample_size, verbosity=False):
    result_list = []
    for single_sample_run in range(sample_size):
        result = single_run(cfg)
        print(result)
        result_list.append(result)
    if verbosity:
        print(Result(cfg, result_list=result_list))
    write_results(result_list, verbosity)


def multi_run_parallel(cfg, sample_size, verbosity=False):
    values = [cfg] * sample_size
    with multiprocessing.Pool(sample_size) as pool:
    # with multiprocessing.Pool() as pool:
        write_results(pool.map(single_run, values), verbosity)
        # print("starting to run")\
        # return pool.map_async(single_run, values, callback=write_results)


def multi_run(args):
    write_header(args.raw_results_file_path)
    write_header(args.agg_results_file_path)

    start = timer()
    if args.run_mode == 'parallel':
        print(f'starting computations on {multiprocessing.cpu_count()} cores')
        r_list = []
    else:
        print('starting computations in series')

    for code_generation_strategy in args.code_generation_strategy_list:
        assert (code_generation_strategy == CodeGenerationStrategy.LINEAR_CODE)
        for key_size in args.key_size_list:
            for block_size in args.block_size_range:
                num_blocks = key_size // block_size
                for p_err in args.p_err_range:
                    success_rate_range = args.success_rate_range or [1.0 - 1.0/key_size]
                    for success_rate in success_rate_range:
                        max_candidates_num_range = [args.max_candidates_num] or [2 ** i for i in range(math.ceil(math.log(key_size, 2))+2)]
                        for max_candidates_num in max_candidates_num_range:
                            for max_num_indices_to_encode in args.max_num_indices_to_encode_range:
                                for sparsity in args.sparsity_range or [0]:
                                    try:
                                        cfg = ProtocolConfigs(base=args.q, block_length=block_size, num_blocks=num_blocks,
                                                          p_err=p_err,
                                                          success_rate=success_rate,
                                                          max_candidates_num=max_candidates_num,
                                                          indices_to_encode_strategy=IndicesToEncodeStrategy.MOST_CANDIDATE_BLOCKS,
                                                          code_generation_strategy=code_generation_strategy,
                                                          pruning_strategy=args.pruning_strategy,
                                                          sparsity=sparsity,
                                                          fixed_number_of_encodings=args.fixed_number_of_encodings,
                                                          max_num_indices_to_encode=max_num_indices_to_encode,
                                                          radius=args.radius,
                                                          upper_threshold=args.upper_threshold,
                                                          raw_results_file_path=args.raw_results_file_path,
                                                          agg_results_file_path=args.agg_results_file_path,
                                                          timeout=args.cfg_timeout)
                                        print(result.Result(cfg))
                                        if args.run_mode == 'parallel':
                                            # r_list.append(multi_run_parallel(cfg, args.sample_size))
                                            multi_run_parallel(cfg, args.sample_size, verbosity=args.verbosity)
                                        else:
                                            multi_run_series(cfg, args.sample_size, verbosity=args.verbosity)
                                    except TimeoutError:
                                        continue

    # print("started all runs")
    # if args.run_mode == 'parallel':
    #     for r in r_list:
    #         print(r)
    #         print("wait")
    #         print(r.ready())
    #         print(r.get())
    #         # r.wait()
    end = timer()
    print(f'elapsed time: {end - start}')