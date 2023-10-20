from django.db import models
from api.components import Progress, Status, QrCode, Link
from uuid import uuid1
from .mercadopago import MercadoPago

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


class PessoaManager(models.Manager):
    pass


class Pessoa(models.Model):
    nome = models.CharField('Nome', max_length=255)
    cpf = models.CharField('CPF', null=True, blank=True, max_length=255)
    telefone = models.CharField('Telefone', null=True, blank=True, max_length=255)
    observacao = models.TextField('Observação', null=True, blank=True)

    objects = PessoaManager()

    class Meta:
        verbose_name = 'Pessoa'
        verbose_name_plural = 'Pessoas'

    def __str__(self):
        return '{} ({})'.format(self.nome, self.cpf) if self.cpf else self.nome

    def get_cartelas(self):
        qs = Cartela.objects
        return qs.filter(responsavel=self) | qs.filter(posse=self)


class AdministradorManager(models.Manager):
    pass


class Administrador(models.Model):
    pessoa = models.ForeignKey(Pessoa, verbose_name='Pessoa', on_delete=models.CASCADE)

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

    def save(self, *args, **kwargs):
        gerar_cartelas = self.pk is None
        super().save(*args, **kwargs)
        if gerar_cartelas:
            self.gerar_cartelas(qtd_taloes=self.qtd_taloes)

    def gerar_cartelas(self, numero_talao=1, numero_cartela=1, qtd_taloes=10):
        for i in range(1, qtd_taloes+1):
            talao = Talao.objects.create(numero=f'{numero_talao}'.rjust(3, '0'), evento=self)
            for j in range(1, self.qtd_cartela_talao + 1):
                Cartela.objects.create(numero=f'{numero_cartela}'.rjust(5, '0'), talao=talao)
                numero_cartela += 1
            numero_talao += 1


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
    numero_cartelas = models.IntegerField('Número de Cartelas', default=1)
    valor = models.DecimalField('Valor', decimal_places=2, max_digits=9)
    cartelas = models.ManyToManyField(Cartela, verbose_name='Cartelas', blank=True)
    data_hora = models.DateTimeField(verbose_name='Data/Hora', auto_now_add=True)

    uuid = models.CharField('UUID', max_length=100)
    status = models.CharField('Status', max_length=25)
    identifier = models.CharField('Identifier', max_length=25)
    qrcode = models.TextField('QrCode')
    url = models.CharField('URL', max_length=25)

    objects = CompraOnlineManager()

    class Meta:
        verbose_name = 'Compra Online'
        verbose_name_plural = 'Compras Online'

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.uuid = uuid1().hex
            self.evento = Evento.objects.order_by('id').last()
            descricao = 'Compra de cartelas ({})'.format(self.numero_cartelas)
            self.valor = self.numero_cartelas * self.evento.valor_venda_cartela
            dados = MercadoPago().realizar_cobranca_pix(self.nome, self.cpf, descricao, self.valor, self.email)
            self.status = dados['status']
            self.identifier = dados['identifier']
            self.qrcode = dados['qrcode']
            self.url = dados['url']
        super().save(*args, **kwargs)

    def is_confirmada(self):
        return self.status == 'approved'

    def get_qrcode(self):
        return QrCode(self.qrcode)

    def get_link_pagamento(self):
        return Link(self.url)

    def get_status(self):
        if self.is_confirmada():
            return Status('success', 'Confirmada')
        else:
            return Status('warning', 'Pendente')

    def get_status_atual(self):
        if not self.is_confirmada():
            self.status = MercadoPago().consultar_pagamento_pix(self.identifier, self.data_hora)
            self.save()
        return self.get_status()

    def __str__(self):
        return 'Compra {}'.format(self.uuid)


