# -*- coding: utf-8 -*-

import logging
import json

from odoo import api, fields, models, tools


_logger = logging.getLogger(__name__)

class InventoryProductTemplate(models.Model):
    _inherit = "product.template"

    warehouse_quantity = fields.Char(compute='_get_warehouse_quantity', string='Cantidades por almacén')

    inventario_cr = fields.Float(string='Inventario CR')
    inventario_usa = fields.Float(string='Inventario USA')

    def _get_warehouse_quantity(self):
        for record in self:
            warehouse_quantity_text = ''
            product_id = self.env['product.product'].sudo().search([('product_tmpl_id', '=', record.id)])
            if product_id:
                quant_ids = self.env['stock.quant'].sudo().search([('product_id','=',product_id[0].id),('location_id.usage','=','internal')])
                t_warehouses = {}
                for quant in quant_ids:
                    if quant.location_id:
                        if quant.location_id not in t_warehouses:
                            t_warehouses.update({quant.location_id:0})
                        t_warehouses[quant.location_id] += quant.quantity

                tt_warehouses = {}
                for location in t_warehouses:
                    warehouse = False
                    location1 = location
                    while (not warehouse and location1):
                        warehouse_id = self.env['stock.warehouse'].sudo().search([('lot_stock_id','=',location1.id)])
                        if len(warehouse_id) > 0:
                            warehouse = True
                        else:
                            warehouse = False
                        location1 = location1.location_id
                    if warehouse_id:
                        if warehouse_id.name not in tt_warehouses:
                            tt_warehouses.update({warehouse_id.name:0})
                        tt_warehouses[warehouse_id.name] += t_warehouses[location]

                for item in tt_warehouses:
                    if tt_warehouses[item] != 0:
                        warehouse_quantity_text = warehouse_quantity_text + ' ' + item + ': ' + str(tt_warehouses[item])
                record.warehouse_quantity = warehouse_quantity_text

class InventoryPlanningConfig(models.Model):
    _name = 'inventory_planning_config'
    _description = 'Configuración de Planeamiento y manejo'

    name = fields.Char('Configuración')
    location_cr = fields.Many2one('stock.location', string='Ubicación CR')
    location_usa = fields.Many2one('stock.location', string='Ubicación USA')
    product_ids = fields.Many2many('product.product', string='Productos')
    fecha_inicio = fields.Date(string='Fecha inicio')

    @api.multi
    @api.depends()
    def actualizar(self):
        _logger.info('******ACTUALIZAR******')
        for temp in self:
            productos = temp.product_ids
        inventory_planning = self.env['inventory_planning'].search([('company_id', '!=', False)])

        if inventory_planning:
            for planning in inventory_planning:

                _logger.info('PRODUCTO .....%s', planning.name)
                _logger.info('PRODUCTO ID .....%s', planning.product_id.id)
                stock_quant = self.env['stock.quant'].search([('product_id', '=', planning.product_id.id)])

                if stock_quant:
                    for quant in stock_quant:
                        if quant.location_id.id == planning.location_id.id:
                            _logger.info('Inventario en localización.....:%s', quant.location_id.id)
                            vals = {'inventario': quant.quantity}
                            _logger.info('registrar .....%s', vals)
                            planning.write(vals)
                #------------------------------------------------------
                # MOVIMIENTOS DE INVENTARIO
                #------------------------------------------------------
                _logger.info('MOVIMIENTOS DE INVENTARIO.....')
                salidas = self.env['stock.move'].search([
                    ('product_id', '=', planning.product_id.id),
                    ('location_id', '=', planning.location_id.id),
                    ('create_date', '>', temp.fecha_inicio),
                    ('state', 'in', ['assigned', 'confirmed','partially_available']),
                ])

                demanda = 0.0
                pedidos_demanda = 0.0
                pedidos_entregado = 0.0
                pedidos_facturado = 0.0
                pedidos_por_facturar = 0.0
                if salidas:
                    for salida in salidas:
                        if salida.state != 'draf' and salida.state != 'waiting' and  salida.state != 'cancel':
                            #_logger.info('Salida nombre.....: %s', salida.name)
                            #_logger.info('Salida estado.....: %s', salida.state)

                            #_logger.info('Producto salida.....: %s', salida.product_id.name)
                            #_logger.info('Linea pedido.....: %s', salida.sale_line_id.id)
                            #_logger.info('Demanda.....: %s', salida.product_uom_qty)
                            #_logger.info('Remanente.....: %s', salida.remaining_qty)
                            demanda += salida.product_uom_qty
                            #BUSCAR INFORMACIÓN PEDIDO
                            sale_line = self.env['sale.order.line'].search([
                                    ('id', '=', salida.sale_line_id.id),
                            ])
                            if sale_line:
                                for line in sale_line:
                                    #_logger.info('Información pedido.....')
                                    #_logger.info('pedidos_demanda.....%s', line.product_uom_qty)
                                    #_logger.info('pedidos_entregado.....%s', line.qty_delivered)
                                    #_logger.info('pedidos_facturado.....%s', line.qty_invoiced)
                                    #_logger.info('pedidos_por_facturar.....%s', line.qty_to_invoice)

                                    pedidos_demanda += line.product_uom_qty
                                    pedidos_entregado += line.qty_delivered
                                    pedidos_facturado += line.qty_invoiced
                                    pedidos_por_facturar += line.qty_to_invoice

                vals = {
                        'demanda': demanda,
                        'pedidos_demanda': pedidos_demanda,
                        'pedidos_entregado': pedidos_entregado,
                        'pedidos_facturado': pedidos_facturado,
                        'pedidos_por_facturar': pedidos_por_facturar,
                        }
                _logger.info('registrar pedidos.....%s', vals)
                planning.write(vals)

    @api.multi
    @api.depends()
    def crear(self):
        _logger.info('******CREAR PRODUCTOS PARA PLANIAMIENTO******')

        for temp in self:
            productos = temp.product_ids

        for producto in productos:
            stock_quant = self.env['stock.quant'].search([('product_id', '=', producto.id)])
            if stock_quant:
                for quant in stock_quant:
                    _logger.info('buscar location id .....: %s',  quant.location_id.id)

                    location = self.env['stock.location'].search([('id', '=', quant.location_id.id)])
                    _logger.info('location name .....: %s', location.name)
                    _logger.info('location usage .....: %s', location.usage)

                    if location.usage == 'internal':
                        _logger.info('Creer Producto / Location .....')
                        vals = {
                            'inventory_planning_config': temp.id,
                            'company_id': location.company_id.id,
                            'product_id': producto.id,
                            'location_id': quant.location_id.id,
                            'name': producto.name,
                            'inventario': quant.quantity,
                        }
                        _logger.info('datos.....%s', vals)
                        self.env['inventory_planning'].create(vals)

class InventoryPlanning(models.Model):
    _name = 'inventory_planning'
    _description = 'Planeamiento y manejo de inventarios'

    name = fields.Char(string='Nombre', readonly=True)

    inventory_planning_config = fields.Many2one('inventory_planning_config', string='Planeamiento', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template',
                                      related='product_id.product_tmpl_id', readonly=True)

    location_id = fields.Many2one('stock.location', string='Ubicación', readonly=True)

    inventario = fields.Float(required=False, copy=False, readonly=True, string='Inventario')

    ventas = fields.Float(required=False, copy=False, readonly=True, string='Ventas')

    demanda = fields.Float(required=False, copy=False, readonly=True, string='Demanda')

    pedidos_demanda = fields.Float(required=False, copy=False, readonly=True, string='Pedidos Demanda')
    pedidos_entregado = fields.Float(required=False, copy=False, readonly=True, string='Pedidos Entregado')
    pedidos_facturado = fields.Float(required=False, copy=False, readonly=True, string='Pedidos Facturado')
    pedidos_por_facturar = fields.Float(required=False, copy=False, readonly=True, string='Pedidos Por Facturar')

class InventorySalePlanning(models.Model):
    _name = 'inventory_planning_portal_orders'
    _description = 'Solicitudes, Pedidos y Ventas'

    name = fields.Char(string='Nombre', readonly=True)

    inventory_planning_config = fields.Many2one('inventory_planning_config', string='Planeamiento', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template',
                                      related='product_id.product_tmpl_id', readonly=True)

    solicitado_portal = fields.Float(required=False, copy=False, readonly=True, string='Portal (Requested)')
    aprobado_portal = fields.Float(required=False, copy=False, readonly=True, string='Portal (Approved)')
    pedidos_portal = fields.Float(required=False, copy=False, readonly=True, string='Portal Total')

    demanda = fields.Float(required=False, copy=False, readonly=True, string='Demanda')
    pedidos_demanda = fields.Float(required=False, copy=False, readonly=True, string='Demanda')
    pedidos_entregado = fields.Float(required=False, copy=False, readonly=True, string='Entregado')
    pedidos_facturado = fields.Float(required=False, copy=False, readonly=True, string='Facturado')
    pedidos_por_facturar = fields.Float(required=False, copy=False, readonly=True, string='Por Facturar')