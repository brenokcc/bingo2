from api import tasks
from .models import Talao, Cartela
import time


class ExportarCartelasTask(tasks.Task):

    def __init__(self, qs):
        self.qs = qs
        super().__init__()

    def run(self):
        rows = []
        valor = None
        rows.append(('Nº da Cartela', 'Talão', 'Responsável', 'Posse', 'Valor da Cartela', 'Valor da Comissão', 'Situação'))
        for obj in self.iterate(self.qs.order_by('numero')):
            if valor is None:
                valor = obj.talao.evento.get_valor_liquido_cartela()
            rows.append((obj.numero, obj.talao.numero, obj.responsavel.nome if obj.responsavel else '',
                         obj.posse.nome if obj.posse else '', valor, obj.comissao or '0', obj.get_situacao()['label']))
        return self.to_csv_file(rows)


class GerarCartelas(tasks.Task):

    def __init__(self, evento):
        self.evento = evento
        super().__init__()

    def run(self):
        numero = 1
        for i in self.iterate(range(1, self.evento.qtd_taloes+1)):
            talao = Talao.objects.create(numero=f'{i}'.rjust(3, '0'), evento=self.evento)
            for j in range(1, self.evento.qtd_cartela_talao + 1):
                Cartela.objects.create(numero=f'{numero}'.rjust(5, '0'), talao=talao)
                numero += 1
