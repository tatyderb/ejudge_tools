#! /usr/bin/python3

import argparse
import json
import logging
import os
import pathlib
import sys

sys.path.append(os.path.dirname(__file__))
from ej_plot_contest import Params, Data

def get_flat_dict(d, department, stage):
    """
    d = {a1: A1, a2:A2, a3: {b1:B1, b2:B2, b3:{c1:C1, c2:C2}} }
    :param d:
    :param kwargs:
    :return:
    """
    dres = {}
    d1 = {}
    for k in d.keys():
        if k != 'department':
            dres[k] = d[k]
        else:
            dres['department'] = department
            d1 = d['department'][department]

    print(dres)
    print(d1)
    # сначала обрабатываем все ключи высших уровней, потом перезаписываем их уровнем stage
    for st in d1:
        if st != 'stage':
            dres[st] = d1[st]

    dres['stage'] = stage
    dres.update(d1['stage'][stage])
    return dres

def process_data(cfg:Params):
    """
    Обработка данных и вывод результатов
    :param cfg: конфиг, где указано что брать, как обрабатывать и куда класть результаты
    :return:
    """
    # разбираем файл данных
    if args.text_only:
        data = Data(cfg)
        data.print_table()
    else:
        from ej_plotter import DataPlotter
        data = DataPlotter(cfg)
        data.print_table()
        data.plot_all(args.show)


if __name__ == '__main__':

    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(lineno)d  \t%(message)s'
        )

    parser = argparse.ArgumentParser(
        description='Calculate statistics for all Ejudge contests described into config json',
        usage=f'\n\t{sys.argv[0]} cfg_2019.json FRTK dec --text_only',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("config", help="config in json format")
    parser.add_argument("department", help="Department name in config dictionary", default=None, nargs='?')
    parser.add_argument("stage", help="stage name in config dictionary", default=None, nargs='?')
    parser.add_argument("--config_only", help="prevent any data processing, only print resulted config, for debug only!",
                        default=False, action="store_true")
    parser.add_argument("--text_only", help="prevent prot data, use if no matplotlib",
                        default=False, action="store_true")
    parser.add_argument('-v', "--verbose", help="increase verbosity",
                        action="store_true")

    args = parser.parse_args()
    args.show = False   # никогда не показываем интерактивно графики, только сохраняем их в файлы

    if args.verbose:
        print("verbosity turned on")
        logging.getLogger().level = logging.DEBUG

    base_dir = pathlib.Path.cwd()
    config_path = base_dir / args.config
    config_dir = config_path.parent

    with open(config_path, 'r', encoding='utf8') as read_file:
        config = json.load(read_file)
    json.dump(config, indent=4, fp=sys.stdout)

    logging.info(f'file={args.config} dep={args.department} stage={args.stage}')

    departments = config['department'].keys() if args.department is None else [args.department]
    stages = ['test', 'oct', 'dec'] if args.stage is None else [args.stage]

    for dep in departments:
        for st in stages:
            print(dep, st)
            d = get_flat_dict(config, dep, st)
            json.dump(d,indent=4, fp=sys.stdout)
            if d is None:
                logging.warning(f'Config file has not department {dep} and stage {st}')
                continue
            cfg = Params.from_dict(config_dir, d)
            if not args.config_only:
                process_data(cfg)
            logging.info(cfg.output_dir)

            # а теперь данные, не отфильтрованные по задачам. Чтобы два раза не запускать с фильтрованным и нефильтрованным конфигом.
            if d['problems']:

                d['problems'] = ''
                d['output_dir'] = 'res_unfiltered'
                cfg = Params.from_dict(config_dir, d)
                if not args.config_only:
                    process_data(cfg)
                logging.info(cfg.output_dir)


