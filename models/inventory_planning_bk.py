# -*- coding: utf-8 -*-

import logging
import json

from odoo import api, fields, models, tools


_logger = logging.getLogger(__name__)

class InventoryProductTemplate(models.Model):
    _inherit = "product.template"

    warehouse_quantity = fields.Char(compute='_get_warehouse_quantity', string='Warehouse quantity')

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

    name = fields.Char('Planning')
    product_ids = fields.Many2many('product.product', string='Products')
    fecha_inicio = fields.Date(string='From date')
    fecha_fin = fields.Date(string='To date')
    dias = fields.Float(string='Planning days')
    porcentaje = fields.Float(string='Porcentage')
    product_ids = fields.Many2many('product.product', string='Products')
    company_ids = fields.Many2many('res.company', string='Companies')
    locations = fields.Many2many('stock.location', string='Ubicaciones')

    @api.multi
    @api.depends()
    def actualizar(self):
        _logger.info('******ACTUALIZAR******')
        for temp in self:
            productos = temp.product_ids

        inventory_planning = self.env['inventory_planning'].search([('inventory_planning_config', '=', temp.id)])

        if inventory_planning:
            for planning in inventory_planning:

                _logger.info('PRODUCTO .....%s', planning.product_id.name)
                _logger.info('PRODUCTO ID .....%s', planning.product_id.id)

                #ACTUALIZAR EXISTENCIAS EN CADA UBICACION
                locations = planning.inventory_planning_location
                _logger.info('Inventario en ubicaciones.....')

                inventario_total = 0.0
                product_id = self.env['product.product'].sudo().search([('product_tmpl_id', '=', planning.product_tmpl_id.id)])

                if product_id:
                    localizaciones = planning.inventory_planning_location

                    for localizacion in localizaciones:
                        _logger.info('Ubicacion.....%s', localizacion.name)

                        inventario = 0.0
                        ubicacion = ''
                        quant_ids = self.env['stock.quant'].sudo().search(
                            [('product_id', '=', product_id[0].id),
                             ('location_id', '=', localizacion.location_id.id),
                             ('location_id.usage', '=', 'internal')],)

                        if quant_ids:

                            for quant in quant_ids:
                                location_name = quant.location_id.location_id.name + '/' + quant.location_id.name
                                location_usage = quant.location_id.usage
                                ubicacion_id = quant.location_id.id
                                ubicacion_nombre = location_name
                                _logger.info('location id .....: %s', ubicacion_id)
                                _logger.info('location name .....: %s', location_name)
                                _logger.info('location usage .....: %s', location_usage)

                                if ubicacion == ubicacion_id:
                                    inventario += quant.quantity
                                else:
                                    inventario = quant.quantity

                                inventario_total += quant.quantity
                                _logger.info('inventario .....: %s', inventario)
                                ubicacion = ubicacion_id

                        localizacion.inventario = inventario

                    _logger.info('+++++++++INVENTARIO TOTAL.....%s', inventario_total)
                # ------------------------------------------------------
                # ORDENES DE VENTAS
                # ------------------------------------------------------
                _logger.info('PORTAL ORDERS.....')
                pedidos_portal = 0.0
                try:
                    #Buscar pedidos de portal
                    buscar_pedidos_portal = self.env['portal.sale.order'].search([
                        ('company_id', '=', planning.company_id.id),
                        ('create_date', '>', temp.fecha_inicio),
                        ('state', 'in', ['approved']),
                    ])
                    for pedido_portal in buscar_pedidos_portal:
                        #Buscar líneas de pedidos de portal
                        lineas_pedidos_portal = self.env['portal.sale.order.line'].search([
                            ('product_id', '=', planning.product_id.id),
                            ('create_date', '>', temp.fecha_inicio),
                            ('order_id', '=', pedido_portal.id),
                        ])
                        for linea_pedido_portal in lineas_pedidos_portal:
                            if linea_pedido_portal.product_id == planning.product_id.id:
                                pedidos_portal += linea_pedido_portal.qty

                    _logger.info('Total pedidos portal.....%s', pedidos_portal)

                except:
                    _logger.info('Error al consultar pedidos de portal.....')

                #------------------------------------------------------
                # ORDENES DE VENTAS
                #------------------------------------------------------
                _logger.info('LINEAS DE PEDIDOS DE VENTAS INVENTARIO.....')
                ordenes = self.env['sale.order.line'].search([
                    ('company_id', '=', planning.company_id.id),
                    ('product_id', '=', planning.product_id.id),
                    ('create_date', '>', temp.fecha_inicio),
                    ('state', 'in', ['sale', 'done']),
                ])

                demanda = 0.0
                remanente = 0.0
                entregado = 0.0
                facturado = 0.0
                por_facturar = 0.0
                if ordenes:
                    _logger.info('Analizar líneas pedidos de ventas.....')
                    for orden in ordenes:
                        demanda += orden.product_uom_qty
                        entregado += orden.qty_delivered
                        facturado += orden.qty_invoiced
                        por_facturar += orden.qty_to_invoice
                    remanente = demanda - entregado

                vals = {
                        'inventario': inventario_total,
                        'pedidos_portal': pedidos_portal,
                        'demanda': demanda,
                        'remanente': remanente,
                        'entregado': entregado,
                        'facturado': facturado,
                        'por_facturar': por_facturar,
                        }
                _logger.info('registrar pedidos.....%s', vals)
                planning.write(vals)

                # ------------------------------------------------------
                # ORDENES DE COMPRAS
                # ------------------------------------------------------
                _logger.info('LINEAS DE PEDIDOS DE COMPRA.....')
                lineas_ordenes = self.env['purchase.order.line'].search([
                    ('company_id', '=', planning.company_id.id),
                    ('product_id', '=', planning.product_id.id),
                    ('create_date', '>', temp.fecha_inicio),
                    ('state', 'in', ['purchase', 'done']),
                ])

                compras = 0.0
                compras_recibido = 0.0
                compras_facturado = 0.0
                compras_total = 0.0

                if lineas_ordenes:
                    _logger.info('Analizar líneas pedidos de compras.....')
                    for linea_orden in lineas_ordenes:
                        # Buscar la orden de compra para verificar la fecha
                        _logger.info('linea pedido de compra.....%s', linea_orden)

                        ordenes = self.env['purchase.order.line'].search([
                            ('id', '=', linea_orden.order_id.id),
                        ])

                        for orden in ordenes:
                            _logger.info('pedido de compra.....%s', linea_orden)
                            _logger.info('fecha configuración.....%s', temp.fecha_inicio)
                            _logger.info('fecha planificada.....%s', orden.date_planned.date())

                            if orden.date_planned.date() >= temp.fecha_inicio:
                                compras += linea_orden.product_uom_qty
                                compras_recibido += linea_orden.qty_received
                                compras_facturado += linea_orden.qty_invoiced
                                compras_total += linea_orden.price_total

                vals = {
                    'compras': compras,
                    'compras_recibido': compras_recibido,
                    'compras_facturado': compras_facturado,
                    'compras_total': compras_total,
                }
                _logger.info('registrar compras.....%s', vals)
                planning.write(vals)


    @api.multi
    @api.depends()
    def crear(self):
        _logger.info('******CREAR PRODUCTOS PARA PLANIAMIENTO******')

        for temp in self:
            companies = temp.company_ids
            productos = temp.product_ids

        for company in companies:
            _logger.info('Company .....: %s', company.name)

            for producto in productos:
                _logger.info('Producto.....%s', producto.name)

                # BUSCAR SI EXISTE EN EL PLANEAMIENTO EL PRODUCTO


                inventory_planning = self.env['inventory_planning'].search(
                    [('inventory_planning_config', '=', temp.id),
                     ('product_id', '=', producto.id),
                     ('company_id', '=', company.id),
                     ])
                vals = {'inventory_planning_config': temp.id,
                        'company_id': company.id,
                        'product_id': producto.id,
                        'name': producto.name,
                        }
                _logger.info('############################')
                _logger.info('Producto.....%s', vals)

                if not inventory_planning:
                    # CREAR UN PRODUCTO POR COMPAÑÍA SI TIENE LOCALIZACIÓN CON EXISTENCIAS
                    inventory_planning = self.env['inventory_planning'].create(vals)
                    _logger.info('creado.....')
                else:
                    inventory_planning.write(vals)
                    _logger.info('actualizado.....')
                _logger.info('############################')

                stock_quant = self.env['stock.quant'].sudo().search(
                            [('company_id', '=', company.id),
                             ('product_id', '=', producto.id),
                             ('location_id.usage', '=', 'internal')])

                ubicacion_id = ''
                ubicacion = ''
                nombre = ''
                inventario = 0.0
                inventario_total = 0.0

                if stock_quant:
                    for quant in stock_quant:

                        location_name = quant.location_id.location_id.name + '/' + quant.location_id.name
                        location_usage = quant.location_id.usage
                        ubicacion_id = quant.location_id.id
                        ubicacion_nombre = location_name
                        _logger.info('location id .....: %s', ubicacion_id)
                        _logger.info('location name .....: %s', location_name)
                        _logger.info('location usage .....: %s', location_usage)

                        if ubicacion == ubicacion_id:
                            inventario += quant.quantity
                        else:
                            inventario = quant.quantity

                        inventario_total += quant.quantity

                        _logger.info('inventario .....: %s', inventario)


                        inventory_planning_location = self.env['inventory_planning_location'].search(
                            [('inventory_planning', '=', inventory_planning.id),
                             ('location_id', '=', ubicacion_id),
                             ])

                        vals = {'inventory_planning': inventory_planning.id,
                                'location_id': ubicacion_id,
                                'name': ubicacion_nombre,
                                'inventario': inventario,
                                }

                        _logger.info('############################')
                        _logger.info('Ubicación.....%s', vals)
                        if not inventory_planning_location:
                            self.env['inventory_planning_location'].create(vals)
                            _logger.info('creado.....')
                        else:
                            inventory_planning_location.write(vals)
                            _logger.info('actualizado.....')
                        _logger.info('############################')

                        ubicacion = ubicacion_id

                    _logger.info('----->>>>> inventario total .....: %s', inventario_total)
                    inventory_planning.inventario = inventario_total









class InventoryPlanning(models.Model):
    _name = 'inventory_planning'
    _description = 'Planeamiento y manejo de inventarios'

    name = fields.Char(string='Name', readonly=True)

    inventory_planning_config = fields.Many2one('inventory_planning_config', string='Planning', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template',
                                      related='product_id.product_tmpl_id', readonly=True)

    inventory_planning_location = fields.One2many('inventory_planning_location', 'inventory_planning',string='Locations', ondelete = 'cascade')


    inventario = fields.Float(required=False, copy=False, readonly=True, string='Inventory')
    demanda = fields.Float(required=False, copy=False, readonly=True, string='Ordered Qty')
    remanente = fields.Float(required=False, copy=False, readonly=True, string='Back Orders')

    compras = fields.Float(required=False, copy=False, readonly=True, string='PO Qty')
    compras_recibido = fields.Float(required=False, copy=False, readonly=True, string='PO Received Qty')
    compras_facturado = fields.Float(required=False, copy=False, readonly=True, string='PO Billed Qty')
    compras_total = fields.Float(required=False, copy=False, readonly=True, string='Purchase Total')

    pedidos_portal = fields.Float(required=False, copy=False, readonly=True, string='Portal Demand')

    entregado = fields.Float(required=False, copy=False, readonly=True, string='Delivered Quantity')
    facturado = fields.Float(required=False, copy=False, readonly=True, string='Invoiced Quantity')
    por_facturar = fields.Float(required=False, copy=False, readonly=True, string='Pending to bill')



class InventoryPlanningLocations(models.Model):
    _name = 'inventory_planning_location'
    _description = 'Ubicación de inventario'

    name = fields.Char(string='Nombre', readonly=True)
    inventory_planning = fields.Many2one('inventory_planning',string='Product Planning', readonly=True)
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)
    inventario = fields.Float(required=False, copy=False, readonly=True, string='Inventary')