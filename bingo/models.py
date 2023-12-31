import os
from django.db import models
from api.components import Progress, Status, QrCode, Link, Map, Steps
from .mercadopago import MercadoPago
from uuid import uuid1


class MeioPagamentoManager(models.Manager):
    pass


class MeioPagamento(models.Model):
    nome = models.CharField('Nome', max_length=255)

    objects = MeioPagamentoManager()

    class Meta:
        verbose_name = 'Meio de Pagamento'
        verbose_name_plural = 'Meios de Pagamento'

    def __str__(self):
        return self.nome

    def has_permission(self, user):
        return user.is_superuser or user.roles.contains('adm')


class PessoaManager(models.QuerySet):
    pass


class Pessoa(models.Model):
    nome = models.CharField('Nome', max_length=255)
    cpf = models.CharField('CPF', null=True, blank=True, max_length=255)
    telefone = models.CharField('Telefone', null=True, blank=True, max_length=255)
    observacao = models.TextField('Observação', null=True, blank=True)

    objects = PessoaManager().as_manager()

    class Meta:
        verbose_name = 'Pessoa'
        verbose_name_plural = 'Pessoas'

    def __str__(self):
        return '{} ({})'.format(self.nome, self.cpf) if self.cpf else self.nome

    def get_cartelas(self):
        qs = Cartela.objects
        return qs.filter(responsavel=self) | qs.filter(posse=self)

    def get_mapa(self):
        return Map(-5.8496847,-35.2038551)

    def get_steps(self):
        steps = Steps('check')
        steps.append('Etapa 01', True)
        steps.append('Etapa 02', True)
        steps.append('Etapa 03', False)
        steps.append('Etapa 04', False)
        steps.append('Etapa 05', False)
        return steps


class AdministradorManager(models.Manager):
    pass


class Administrador(models.Model):
    pessoa = models.ForeignKey(Pessoa, verbose_name='Pessoa', on_delete=models.CASCADE, addable=True)

    objects = AdministradorManager()

    class Meta:
        verbose_name = 'Administrador'
        verbose_name_plural = 'Administradores'

    def __str__(self):
        return '{}'.format(self.pessoa)


class EventoManager(models.Manager):
    pass


class Evento(models.Model):
    nome = models.CharField('Nome', max_length=255)
    data = models.DateField('Data')
    operadores = models.ManyToManyField(Pessoa, verbose_name='Operadores')

    qtd_taloes = models.IntegerField('Quantidade de Talões')
    qtd_cartela_talao = models.IntegerField('Quantidade de Cartela por Talão')
    valor_venda_cartela = models.DecimalField('Valor de Venda da Cartela', decimal_places=2, max_digits=9)
    valor_comissao_cartela = models.DecimalField('Valor Máximo da Comissão por Cartela', decimal_places=2, max_digits=9)

    objects = EventoManager()

    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'

    def __str__(self):
        return self.nome


    def get_valor_liquido_cartela(self):
        return self.valor_venda_cartela - self.valor_comissao_cartela

    def get_cartelas(self):
        return Cartela.objects.filter(talao__evento=self)

    def get_cartelas_distribuidas(self):
        return self.get_cartelas().filter(responsavel__isnull=False)

    def get_total_taloes(self):
        return self.get_total_cartelas() // self.qtd_cartela_talao

    def get_percentual_cartela_distribuida(self):
        return Progress(100 * self.get_cartelas_distribuidas().count() / self.get_total_cartelas())

    def get_percentual_cartela_paga(self):
        return Progress(100 * self.get_cartelas_distribuidas().filter(realizou_pagamento=True).count() / self.get_total_cartelas())

    def get_total_cartelas_distribuidas(self):
        return self.get_cartelas_distribuidas().count()

    def get_receita_esperada(self):
        return self.get_cartelas_distribuidas().count() * self.get_valor_liquido_cartela()

    def get_valor_recebido_venda(self):
        return self.get_cartelas_distribuidas().filter(realizou_pagamento=True).count() * self.get_valor_liquido_cartela()

    def get_valor_recebido_doacao(self):
        qs = self.get_cartelas_distribuidas().filter(realizou_pagamento=True)
        return qs.count() * self.valor_comissao_cartela - qs.sum('comissao')

    def get_valor_receber(self):
        return self.get_receita_esperada() - self.get_valor_recebido_venda()

    def get_valor_perdido(self):
        return self.get_cartelas().filter(responsavel__isnull=False, realizou_pagamento=False).count() * self.get_valor_liquido_cartela()

    def get_receita_final(self):
        return self.get_valor_recebido_venda() + self.get_valor_recebido_doacao()

    def get_total_cartelas(self):
        return self.get_cartelas().count()

    def gerar_cartelas_online(self, numero_cartelas):
        cartelas = []
        talao = Talao.objects.get_or_create(numero='000', evento=self)[0]
        total = talao.cartela_set.count()
        for numero_cartela in range(total, total+numero_cartelas):
            cartelas.append(Cartela.objects.create(numero=f'{numero_cartela+1}'.rjust(5, '0'), talao=talao))
        return cartelas


class TalaoManager(models.Manager):
    pass

class Talao(models.Model):
    numero = models.CharField('Número', max_length=255)
    evento = models.ForeignKey(Evento, verbose_name='Evento', on_delete=models.CASCADE)

    objects = TalaoManager()

    class Meta:
        verbose_name = 'Talão'
        verbose_name_plural = 'Talões'

    def __str__(self):
        return self.numero

    def has_permission(self, user):
        return user.is_superuser or user.roles.contains('adm')


class CartelaManager(models.QuerySet):
    def pendentes_distribuicao(self):
        return self.filter(responsavel__isnull=True)

    def pagas(self):
        return self.filter(responsavel__isnull=False, realizou_pagamento=True)

    def pendentes_pagamento(self):
        return self.filter(responsavel__isnull=False, realizou_pagamento__isnull=True)

    def nao_pagas(self):
        return self.filter(responsavel__isnull=False, realizou_pagamento=False)

    def pagas_com_comissao(self):
        return self.pagas().filter(comissao__gt=0)

    def pagas_sem_comissao(self):
        return self.pagas().filter(recebeu=0)

    def get_valor_liquido_cartela(self):
        return self.first().talao.evento.get_valor_liquido_cartela() if self.exists() else 0

    def get_valor_pago(self):
        return self.pagas().count() * self.get_valor_liquido_cartela()

    def get_valor_pendente_pagamento(self):
        return self.pendentes_pagamento().count() * self.get_valor_liquido_cartela()

    def get_valor_nao_pago(self):
        return self.nao_pagas().count() * self.get_valor_liquido_cartela()


class Cartela(models.Model):
    numero = models.CharField('Número', max_length=255)
    talao = models.ForeignKey(Talao, verbose_name='Talão', on_delete=models.CASCADE)

    responsavel = models.ForeignKey(Pessoa, verbose_name='Responsável', null=True, on_delete=models.CASCADE)
    realizou_pagamento = models.BooleanField('Realizou Pagamento', null=True)
    meio_pagamento = models.ForeignKey(MeioPagamento, verbose_name='Meio de Pagamento', null=True, blank=True, on_delete=models.CASCADE)
    comissao = models.DecimalField('Comissão', default=0, decimal_places=2, max_digits=9)

    posse = models.ForeignKey(Pessoa, verbose_name='Posse', null=True, related_name='possecartela_set', blank=True, on_delete=models.CASCADE)

    objects = CartelaManager()

    class Meta:
        verbose_name = 'Cartega'
        verbose_name_plural = 'Cartelas'

    def __str__(self):
        return self.numero

    def get_evento(self):
        return self.talao.evento

    def get_situacao(self):
        if self.responsavel_id is None:
            return Status('primary', 'Aguarando Distribuição')
        elif self.realizou_pagamento is None:
            return Status('warning', 'Aguarando Prestação de Contas')
        elif self.realizou_pagamento:
            if self.comissao > 0:
                return Status('success', 'Vendida com Comissão')
            else:
                return Status('success', 'Vendida sem Comissão')
        else:
            return Status('danger', 'Pagamento não Realizado')


class CompraOnlineManager(models.Manager):
    pass


class CompraOnline(models.Model):
    nome = models.CharField('Nome', max_length=255)
    cpf = models.CharField('CPF', null=True, blank=True, max_length=255)
    telefone = models.CharField('Telefone', null=True, blank=True, max_length=255)
    email = models.CharField('E-mail', null=True, blank=True, max_length=255)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    valor = models.DecimalField('Valor', decimal_places=2, max_digits=9)
    numero_cartelas = models.IntegerField('Número de Cartelas', default=1)
    cartelas = models.ManyToManyField(Cartela, verbose_name='Cartelas', blank=True)
    data_hora = models.DateTimeField(verbose_name='Data/Hora', auto_now_add=True)

    uuid = models.CharField('UUID', max_length=100)
    status = models.CharField('Status', max_length=25)
    url = models.CharField('URL', max_length=255)

    objects = CompraOnlineManager()

    class Meta:
        verbose_name = 'Compra Online'
        verbose_name_plural = 'Compras Online'

    def save(self, *args, **kwargs):
        pk = self.pk
        if pk is None:
            self.evento = Evento.objects.order_by('id').last()
            self.uuid = uuid1().hex
            descricao = 'Compra de cartelas ({})'.format(self.numero_cartelas)
            self.valor = self.numero_cartelas * self.evento.valor_venda_cartela
            callback = '{}/api/v1/visualizar_compra_online/?uuid={}'.format(
                os.environ.get('SITE_URL', 'http://localhost:8000'), self.uuid
            )
            dados = MercadoPago().realizar_checkout_pro(
                self.nome, self.cpf, descricao, self.valor, self.email, self.uuid, callback
            )
            self.uuid = dados['ref']
            self.url = dados['url']
        super().save(*args, **kwargs)

    def is_confirmada(self):
        return self.status == 'approved'

    def get_link_pagamento(self):
        return Link(self.url)

    def get_status(self):
        if self.is_confirmada():
            return Status('success', 'Confirmada')
        else:
            return Status('warning', 'Pendente')

    def atualizar_situacao(self):
        if not self.is_confirmada():
            self.status = MercadoPago().consultar_pagamento(self.uuid, self.data_hora)
            self.save()
        if self.is_confirmada() and not self.cartelas.exists():
            evento = Evento.objects.order_by('data').last()
            self.cartelas.set(evento.gerar_cartelas_online(self.numero_cartelas))
            pessoa = Pessoa.objects.get_or_create(cpf='000.000.000-00', nome='Compra Online')[0]
            meio_pagamento = MeioPagamento.objects.get_or_create(nome='Mercado Pago')[0]
            self.cartelas.update(responsavel=pessoa, meio_pagamento=meio_pagamento, realizou_pagamento=True, comissao=0)

    def get_status_atual(self):
        if not self.is_confirmada():
            self.atualizar_situacao()
        return self.get_status()

    def get_numeros_cartelas(self):
        return ', '.join(self.cartelas.values_list('numero', flat=True))

    def get_cartelas(self):
        return self.cartelas.fields('id', 'numero', 'meio_pagamento')

    def __str__(self):
        return 'Compra {}'.format(self.uuid)


