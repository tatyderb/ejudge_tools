"""
Рисует круговые диаграммы оценок в каждой школе и сохраняет их в указанной директории.
python3 plot_semestr_data.py example_data.csv output_dir 'осенний семестр 2019 года'
"""

import argparse
import datetime
import csv
import json
import logging
import os
import pathlib
import sys

import matplotlib.pyplot as plt
import numpy as np

MARK = 'Оценка'

PIE_COLORS = {
    '10':'#127622',
    '9':'#069a2e',
    '8':'#77bc65',
    '7':'#3465a4',
    '6':'#729fcf',
    '5':'#b4c7dc',
    '4':'#ffff38',
    '3':'#ffffa6',
    '2':'#f10d0c',
    '1':'#f10d0c',
    'н/я':'#ff6d6d'
}

def process_data(csv_path):
    # читаем cvs файл
    with open(csv_path, encoding="utf8") as fh:
        rd = csv.DictReader(fh, delimiter=';')
        data = [dict(row) for row in rd]
    logging.debug((data))
    
    d = {department:{} for department in data[0].keys() if department != MARK}
    for r in data[1:]:
        mark = r[MARK]
        for department, count in r.items():
            if department == MARK:
                continue
            d[department][mark] = int(count)

    return d

def plot_pie1(output_dir, department, marks, title, show=True):
    """
    Рисует 1 диаграмму для факультета
    """

    
    counts = [count for count in marks.values()]
    labels = [f'{mark} - {count}' for mark, count in marks.items()]
    pie_colors = [PIE_COLORS[mark] for mark in marks]

    file_name = ''

    # Make figure and axes
    fig, ax = plt.subplots()

    # The slices will be ordered and plotted counter-clockwise.
    patches, texts = plt.pie(counts, colors=pie_colors, startangle=90)
    plt.legend(patches, labels, loc="best")
    # Set aspect ratio to be equal so that pie is drawn as a circle.
    plt.axis('equal')
    #plt.tight_layout()

    ax.set_title(f'{department} {title}')

    if show:
        plt.show()

    filename = f'{title}_{department}_pie.png'
    filename = output_dir.joinpath(filename).resolve()
    fig.savefig(filename, format='png', bbox_inches='tight', pad_inches=0)
    plt.close(fig)


    
def plot_pies(output_dir, d, title, show=True):
    print(d)
    
    """
    Рисует pie-диаграмму для по каждому факультету
    :param show: - показывать графики интерактивно (в файл сохраняется всегда)
    """
    
    for department, marks in d.items():
        plot_pie1(output_dir, department, marks, title, show)



def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(lineno)d  \t%(message)s'
        )

    parser = argparse.ArgumentParser(
        description='Plot chart for semestr results per departments',
        usage=f'\n\t{sys.argv[0]} ./data/2019_1.csv ./res/2019',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("csv", help="data in csv format")
    parser.add_argument("output_dir", help="directory for resulted plots", default='.', nargs='?')
    
    parser.add_argument("title", help="title in plots", default='', nargs='?')

    parser.add_argument('-v', "--verbose", help="increase verbosity",
                        action="store_true")

    args = parser.parse_args()

    if args.verbose:
        print("verbosity turned on")
        logging.getLogger().level = logging.DEBUG

    base_dir = pathlib.Path.cwd()
    output_parent = base_dir / args.output_dir

    # директория выходных данных, создаем ее
    logging.info(f'Output directory is {output_parent.resolve()}')
    if not output_parent.exists():
        logging.info(f'Make directory is {output_parent.resolve()}')
        output_parent.mkdir(parents=True)
    
    if not output_parent.is_dir():
        logging.error(f'Output path should be directory, {output_parent} is not directory')
        sys.exit(1)
        
    d = process_data(base_dir / args.csv)
    plot_pies(output_parent, d, args.title)

if __name__ == '__main__':
    main()