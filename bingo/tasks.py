from api import tasks
from .models import Talao, Cartela
import time

class GerarCartelas(tasks.Task):

    def __init__(self, evento):
        self.evento = evento
        super().__init__()

    def run(self):
        for i in self.iterate(range(1, self.evento.qtd_taloes+1)):
            talao = Talao.objects.create(numero=f'{self.numero_talao}'.rjust(3, '0'), evento=self.evento)
            for j in range(1, self.evento.qtd_cartela_talao + 1):
                Cartela.objects.create(numero=f'{self.numero_cartela}'.rjust(5, '0'), talao=talao)
                self.numero_cartela += 1
            self.numero_talao += 1
