from ej_plot_contest import Data, Params, ProblemName

import logging
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

class DataPlotter(Data):
    def __init__(self, config:Params, csv_file:str, delimiter, duration=None, login_list=None):
        super().__init__(config, csv_file, delimiter, duration, login_list)

    @staticmethod
    def get_colors(cmp, n:int):
        """
        return list of n colors from colormap named cm
        :param cm: - name of colormap
        :param n: - number of colors (should be less then colormap color quantity
        :return: list of n colors
        """
        return list(cmp(np.arange(n)))

    def plot_all(self, show=True):
        """
        Рисует и сохраняет все графики по прочитанным данным
        :param show: - показывать графики интерактивно (в файл сохраняется всегда)
        """
        self.plot_department(show)
        for gr in self.groups:
           self.plot_group(gr, show)
        for prob in self.headers:
            self.plot_prob_pie(prob, show_unsolved=True, show=show)
            #self.plot_prob_pie(prob, show_unsolved=False, show=show)


    def plot_department(self, show=True):
        """
        Рисует и сохраняет в файл данные по всему факультету (stacked bar по каждой группе студентов) для всех задач
        :param show: - показывать графики интерактивно (в файл сохраняется всегда)
        """
        department = self.cfg.department    # department='DPQE'
        preps = self.cfg.preps              # preps = {'705': 'Иванов'}
        headers = ['студентов'] + [h.label for h in self.headers] # headers = ['студентов', 'C', 'Cmem', 'D', 'F', 'E', 'Emem']
        logging.debug(f'plot department {department} for preps {preps} with headers {headers}')

        # номера групп в нужной последовательности
        groups = self.groups

        # делаем из self.data матрицу, строки - группы, столбцы - задачи ydata[group][prob]
        # и добавляем первым столбцом ydata[gr][0] количество студентов в группе
        ydata = np.array([self.data_group(gr) for gr in groups])

        # данные по задачам
        # столбцы 0, 1, 2, .. до последней задачи, первый столбец - общее кооличество студентов в группе
        xdata = np.arange(len(headers))

        logging.debug(xdata)
        logging.debug(ydata)
        logging.debug(groups)

        width = 0.35  # the width of the bars: can also be len(x) sequence

        fig, ax = plt.subplots()

        logging.debug(f'ydata {ydata}')

        y_bottom = np.zeros(len(ydata[0]), dtype=int)

        for i in range(ydata.shape[0]):
            gr = groups[i]
            logging.debug(f'group={gr} preps={preps}')
            logging.debug(f'{gr} {preps[gr]}')
            p = ax.bar(xdata, ydata[i], width, label=f'{gr} {preps[gr]}', bottom=y_bottom)  # , color=colors[i]
            y_bottom = y_bottom + ydata[i]
            logging.debug(f'y_bottom = {y_bottom}')

        # числа сверху столбцов, без первого
        x = xdata[1:]
        y = y_bottom[1:]
        for i in range(len(x)):
            ax.annotate(str(y[i]),  # this is the text
                        (x[i], y[i]),  # this is the point to label
                        textcoords="offset points",  # how to position the text
                        xytext=(0, 10),  # distance from text to points (x,y)
                        ha='center')  # horizontal alignment can be left, right or center
        ax.set_xticks(xdata)
        ax.set_xticklabels(headers)
        ax.set_title(f'{department} всего')
        ax.legend()

        if show:
            plt.show()
        filename = f'{department}_all.png'
        filename = self.cfg.output_dir.joinpath(filename).resolve()
        fig.savefig(filename, format='png', bbox_inches='tight', pad_inches=0)

    def plot_group(self, group:str, show=True):
        """
        Рисует и сохраняет в файл данные по 1 группе студентов
        :param group: - номер группы
        :param show: - показывать графики интерактивно (в файл сохраняется всегда)
        """
        department = self.cfg.department    # department='DPQE'
        headers = ['студентов'] + [h.label for h in self.headers] # headers = ['студентов', 'C', 'Cmem', 'D', 'F', 'E', 'Emem']
        colors = ['lightgray'] + DataPlotter.get_colors(plt.cm.tab10, len(headers)-1)   # gray - for student numbers
        logging.debug(f'plot GROUP group {group} of {department} department with headers {headers}')

        # данные по задачам
        xdata = np.arange(len(headers))
        ydata = self.data_group(group)

        fig, ax = plt.subplots()

        # рисуем столбик студентов и столбики задач
        # каждая задача отдельным графиком, чтобы получить легенду по отдельным задачам, иначе можно было бы одним
        # ax.bar(x, y, label, colors)
        # и еще числа сверху каждого столбика - аннотации
        for x, y in enumerate(ydata):
            ax.bar([x + 1], [y], label=headers[x], color=colors[x])

            ax.annotate(str(y),  # this is the text
                        (x + 1, y),  # this is the point to label
                        textcoords="offset points",  # how to position the text
                        xytext=(0, 1 if x == 0 else 10),  # distance from text to points (x,y)
                        ha='center')  # horizontal alignment can be left, right or center

        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.set_xticks(xdata+1)
        ax.set_xticklabels(headers)
        ax.set_title(f'{department} {group} {self.cfg.preps[group]}')
        ax.legend()
        if show:
            plt.show()

        filename = f'{department}_{group}.png'
        filename = self.cfg.output_dir.joinpath(filename).resolve()
        fig.savefig(filename, format='png', bbox_inches='tight', pad_inches=0)


    def plot_prob_pie(self, prob_name, show_unsolved=False, show=True):
        """
        Рисует pie-диаграмму для задачи prob_name по количеству ее решивших по группам.
        :param prob_name: = ProblemName('Cmem-', department) - для какой задачи будем брать данные
        :param show_unresolved: - рисовать серым сектор сколько студентов НЕ решило эту задачу или рисуем только решения
        :param show: - показывать графики интерактивно (в файл сохраняется всегда)
        """

        # номера групп в нужной последовательности
        groups = list(self.groups)
        department = self.cfg.department    # department='DPQE'
        logging.debug(f'plot PROBLEM {prob_name} for groups {groups} of {department} department')

        fracs = [self.data[g].get(prob_name.fullname, 0) for g in groups]
        logging.debug(fracs)
        explodes = [0] * len(fracs)
        logging.debug(explodes)
        pie_colors =  DataPlotter.get_colors(plt.cm.tab10, len(fracs)) + ['lightgray']

        file_name = ''
        if show_unsolved:
            file_name = '100'
            total_students = sum(self.totals.values())
            logging.debug(total_students)
            solved = sum(fracs)
            unsolved = total_students - solved
            fracs.append(unsolved)
            groups.append('unsolved')
            explodes.append(0.01)

        # Make figure and axes
        fig, ax = plt.subplots()

        # The slices will be ordered and plotted counter-clockwise.
        labels = [f'{fracs[i]} - {groups[i]}' for i in range(len(fracs))]
        patches, texts = plt.pie(fracs, colors=pie_colors, startangle=90)
        plt.legend(patches, labels, loc="best")
        # Set aspect ratio to be equal so that pie is drawn as a circle.
        plt.axis('equal')
        #plt.tight_layout()

        ax.set_title(f'{department} {prob_name.label}')

        if show:
            plt.show()

        filename = f'{department}_{prob_name.label}_pie{file_name}.png'
        filename = self.cfg.output_dir.joinpath(filename).resolve()
        fig.savefig(filename, format='png', bbox_inches='tight', pad_inches=0)
