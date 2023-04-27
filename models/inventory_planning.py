# -*- coding: utf-8 -*-

import logging
import json

from odoo import api, fields, models, tools


_logger = logging.getLogger(__name__)


class InventoryPlanningStockQuant(models.Model):
    _inherit = 'stock.quant'

    def view_reserved_quantity(self):
        sml_ids = self.env['stock.move.line'].search([
            ('product_id', '=', self.product_id.id),
            ('location_id', '=', self.location_id.id),
            ('state', 'not in', ['done', 'cancel']),
            ('product_qty', '>', 0)
        ])
        return self.view_reserved_quantity_sml(sml_ids)

    def view_reserved_quantity_sml(self, sml_ids):
        context = {'create': False, 'edit': False}
        tree_view_id = self.env.ref('stock.view_move_line_tree').id
        form_view_id = self.env.ref('stock.view_move_line_form').id
        action = {
            'name': 'Reserved',
            'view_mode': 'form',
            'res_model': 'stock.move.line',
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'view_id': tree_view_id,
            'domain': [('id', 'in', sml_ids.ids)],
            'type': 'ir.actions.act_window',
            'context': context,
            'binding_views': 'form',
            'target': 'new'
        }
        return action

class InventoryPlanningPurchaseLines(models.Model):
    _inherit = 'purchase.order'

    def view_transit(self):
        sml_ids = self.env['purchase.order.line'].search([
            ('product_id', '=', self.product_id.id),
            ('order', '=', self.id),
            ('state', 'in', ['purchase', 'done'])
            ])
        return self.view_transit_sml(sml_ids)

    def view_transit_sml(self, sml_ids):
        context = {'create': False, 'edit': False}
        tree_view_id = self.env.ref('purchase.purchase_order_line_tree').id
        form_view_id = self.env.ref('purchase.purchase_order_line_form2').id
        action = {
            'name': 'Purchases',
            'view_mode': 'form',
            'res_model': 'purchase.order.line',
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'view_id': tree_view_id,
            'domain': [('id', 'in', sml_ids.ids)],
            'type': 'ir.actions.act_window',
            'context': context,
            'binding_views': 'form',
            'target': 'new'
        }
        return action

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def view_reserved_quantity_mw(self):
        sml_ids = self.env['stock.move.line'].search([
            ('product_id', 'in', self.product_variant_ids.ids),
            ('state', 'not in', ['done', 'cancel']),
            ('product_qty', '>', 0)
        ])
        return self.env['stock.quant'].view_reserved_quantity_sml(sml_ids)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def view_reserved_quantity_mw(self):
        sml_ids = self.env['stock.move.line'].search([
            ('product_id', '=', self.id),
            ('state', 'not in', ['done', 'cancel']),
            ('product_qty', '>', 0)
        ])
        return self.env['stock.quant'].view_reserved_quantity_sml(sml_ids)



class InventoryPlanningConfig(models.Model):
    _name = 'inventory_planning_config'
    _description = 'Configuración de Planeamiento y manejo'

    name = fields.Char('Planning')
    product_ids = fields.Many2many('product.product', string='Products')
    fecha_inicio = fields.Date(string='From date')
    fecha_fin = fields.Date(string='To date')
    dias = fields.Float(string='Ideal inventory in days')
    porcentaje = fields.Float(string='Porcentage  back order consider')
    product_ids = fields.Many2many('product.product', string='Products')
    company_ids = fields.Many2many('res.company', string='Companies')
    provider_ids = fields.Many2many('res.partner', string='Providers', domain=[('supplier', '=', True)])

    @api.multi
    @api.depends()
    def cargar_productos_proveedor(self):
        _logger.info('******PROVEEDORES PARA PLANIAMIENTO******')

        for temp in self:
            companies = temp.company_ids
            providers = temp.provider_ids
            products = temp.product_ids

        for provider in providers:
            _logger.info('Proveedor configurado .....: %s', provider.name)

            for company in companies:

                productos = self.env['product.product'].search([('active', '=', True),
                                                                ('company_id', '=', company.id)])

                for producto in productos:
                    _logger.info('Producto.....%s', producto.name)
                    proveedores = producto.seller_ids
                    existe = 'NO'
                    for proveedor in proveedores:
                        _logger.info('provider.id.....: %s', provider.id)
                        _logger.info('proveedor.id.....: %s', proveedor.name.id)

                        if provider.id == proveedor.name.id:
                            agregar = 'SI'
                            _logger.info('verificar si existe producto en planeamiento actual....')
                            for product in products:
                                if product.id == producto.id:
                                    existe = 'SI'
                            _logger.info('Existe.....%s', existe)

                            if existe == 'NO':
                                _logger.info('Agregar producto a planeamiento....')
                                self.product_ids =  [(4, producto.id)]

    @api.multi
    @api.depends()
    def ejecutar(self):
        _logger.info('******PRODUCTOS PARA PLANIAMIENTO******')

        for temp in self:
            companies = temp.company_ids
            productos = temp.product_ids

        inventory_planning_delete = self.env['inventory_planning'].search(
            [('inventory_planning_config', '=', temp.id)])

        for invetory_delete in inventory_planning_delete:
            invetory_delete.unlink()


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

                # ------------------------------------------------------
                # ORDENES DE PORTAL
                # ------------------------------------------------------
                _logger.info('PORTAL ORDERS.....')
                pedidos_portal = 0.0
                pedido_real_orden = 0.0
                pedido_real_portal = 0.0
                diferencia = 0.0
                try:
                    # Buscar pedidos de portal
                    buscar_pedidos_portal = self.env['portal.sale.order'].search([
                            ('company_id', '=', company.id),
                            ('create_date', '>', temp.fecha_inicio),
                            ('state', 'in', ['approved']),
                        ])
                    for pedido_portal in buscar_pedidos_portal:
                        # Buscar líneas de pedidos de portal
                        lineas_pedidos_portal = self.env['portal.sale.order.line'].search([
                                ('product_id', '=', producto.id),
                                ('create_date', '>', temp.fecha_inicio),
                                ('order_id', '=', pedido_portal.id),
                                ])
                        #Ventas asociadas al pedido de portal
                        sale_ids = pedido_portal.sale_ids
                            
                        for linea_pedido_portal in lineas_pedidos_portal:
                            pedidos_portal += linea_pedido_portal.qty
                            pedido_real_portal += linea_pedido_portal.qty
                            
                            for sale_id in sale_ids:
                                _logger.info('buscar linea de pedido de ventas.....%s', sale_id)
                                ordenes = self.env['sale.order.line'].search([
                                ('order_id', '=', sale_id.id),
                                ('product_id', '=', producto.id),
                                ('state', 'in', ['sale', 'done']),
                                ])
                                for orden in ordenes:
                                    _logger.info('cantidad en pedido de ventas.....%s', orden.product_uom_qty)
                                    pedido_real_orden += orden.product_uom_qty
                                _logger.info('cantidad total pedido de ventas.....%s', pedido_real_orden)
                                
                            
                    diferencia = pedido_real_portal - pedido_real_orden
                        
                    _logger.info('Total pedidos portal.....%s', pedidos_portal)
                    vals = {
                        'pedidos_portal': pedidos_portal,
                        'diferencia': diferencia,
                    }
                    _logger.info('registrar pedidos.....%s', vals)
                    inventory_planning.write(vals)

                except Exception as e:
                    _logger.info('Error al consultar pedidos portal.....:%s', str(e))


                
                # ------------------------------------------------------
                # ORDENES DE VENTAS
                # ------------------------------------------------------
                _logger.info('LINEAS DE PEDIDOS DE VENTAS INVENTARIO.....')
                try:
                    ordenes = self.env['sale.order.line'].search([
                                ('company_id', '=', company.id),
                                ('product_id', '=', producto.id),
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
                            'demanda': demanda,
                            'remanente': remanente,
                            'entregado': entregado,
                            'facturado': facturado,
                            'por_facturar': por_facturar,
                            }
                    _logger.info('registrar pedidos.....%s', vals)
                    inventory_planning.write(vals)

                except Exception as e:
                    _logger.info('Error al consultar ordenes de ventas.....:%s', str(e))



                # ------------------------------------------------------
                # PEDIDOS DE COMPRA
                # ------------------------------------------------------
                _logger.info('LINEAS DE PEDIDOS DE COMPRA.....')
                lineas_ordenes = self.env['purchase.order.line'].search([
                        ('company_id', '=', company.id),
                        ('product_id', '=', producto.id),
                        ('create_date', '>', temp.fecha_inicio),
                        ('state', 'in', ['purchase', 'done']),
                        ])

                compras = 0.0
                compras_recibido = 0.0
                compras_facturado = 0.0
                compras_total = 0.0
                transito = 0.0

                if lineas_ordenes:
                    _logger.info('Analizar líneas pedidos de compras.....')
                    for linea_orden in lineas_ordenes:
                        # Buscar la orden de compra para verificar la fecha
                        _logger.info('linea pedido de compra.....%s', linea_orden)

                        ordenes = self.env['purchase.order'].search([
                                ('id', '=', linea_orden.order_id.id),
                                ])

                        for orden in ordenes:
                            #_logger.info('pedido de compra.....%s', linea_orden)
                            #_logger.info('fecha configuración.....%s', temp.fecha_inicio)
                            #_logger.info('fecha planificada.....%s', orden.date_planned.date())

                            if orden.date_planned.date() >= temp.fecha_inicio:
                                compras += linea_orden.product_uom_qty
                                compras_recibido += linea_orden.qty_received
                                compras_facturado += linea_orden.qty_invoiced
                                compras_total += linea_orden.price_total
                                transito = compras - compras_recibido

                vals = {
                        'compras': compras,
                        'compras_recibido': compras_recibido,
                        'compras_facturado': compras_facturado,
                        'compras_total': compras_total,
                        'transito': transito,
                        }
                _logger.info('registrar compras.....%s', vals)
                inventory_planning.write(vals)

                # ------------------------------------------------------
                # INVENTARIO EN UBICACIONES
                # ------------------------------------------------------

                stock_quant = self.env['stock.quant'].sudo().search(
                    [('company_id', '=', company.id),
                     ('product_id', '=', producto.id),
                     ('location_id.usage', '=', 'internal')])

                ubicacion_id = ''
                ubicacion = ''
                nombre = ''
                
                inventario_total = 0.0

                if stock_quant:
                    for quant in stock_quant:
                        inventario = 0.0
                        location_name = quant.location_id.location_id.name + '/' + quant.location_id.name
                        location_usage = quant.location_id.usage
                        ubicacion_id = quant.location_id.id
                        ubicacion_nombre = location_name
                        #_logger.info('location id .....: %s', ubicacion_id)
                        #_logger.info('location name .....: %s', location_name)
                        #_logger.info('location usage .....: %s', location_usage)

                        # BUSCAR SI EXISTE EL PRODUCTO EN EL PLANEAMIENTO
                        inventory_planning_location = self.env['inventory_planning'].search(
                            [('inventory_planning_config', '=', temp.id),
                             ('product_id', '=', producto.id),
                             ('company_id', '=', company.id),
                             ('location_id', '=', ubicacion_id),
                             ])

                        if inventory_planning_location:
                            for inventori_location in inventory_planning_location:
                                inventario = quant.quantity + inventori_location.inventario
                        
                        else:
                            inventario = quant.quantity

                        inventario_total += inventario

                        _logger.info('inventario .....: %s', inventario)

                        #stock_move = self.env['stock.move.line'].sudo().search(
                        #    [('company_id', '=', company.id),
                        #     ('product_id', '=', producto.id),
                        #     ('location_dest_id', '=', ubicacion_id),
                        #     ('date_expected', '>', temp.fecha_inicio)
                        #     ])

                        movimientos = self.env['stock.move.line'].search([
                            ('product_id', '=',  producto.id),
                            ('location_id', '=', ubicacion_id),
                            ('state', 'not in', ['done', 'cancel']),
                            ('product_qty', '>', 0)
                        ])

                        reservado = 0.0

                        for move in movimientos:
                            reservado += move.product_qty

                        vals = {'inventory_planning_config': temp.id,
                                'company_id': company.id,
                                'product_id': producto.id,
                                'location_id': ubicacion_id,
                                'inventario': inventario,
                                'reservado': reservado,
                                'name': producto.name,
                                }

                        _logger.info('############################')
                        _logger.info('Producto ubicación.....%s', vals)

                        if not inventory_planning_location:
                            self.env['inventory_planning'].create(vals)
                            _logger.info('creado.....')
                        else:
                            inventory_planning_location.write(vals)
                            _logger.info('actualizado.....')
                        _logger.info('############################')

                        ubicacion = ubicacion_id

                    _logger.info('----->>>>> inventario total .....: %s', inventario_total)
                    #inventory_planning.inventario = inventario_total



class InventoryPlanning(models.Model):
    _name = 'inventory_planning'
    _description = 'Planeamiento y manejo de inventarios'

    name = fields.Char(string='Name', readonly=True)

    inventory_planning_config = fields.Many2one('inventory_planning_config', string='Planning', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template',
                                      related='product_id.product_tmpl_id', readonly=True)

    location_id = fields.Many2one('stock.location', string='Location', readonly=True)

    inventario = fields.Float(required=False, copy=False, readonly=True, string='Inventory')
    transito = fields.Float(required=False, copy=False, readonly=True, string='Transit')
    reservado = fields.Float(required=False, copy=False, readonly=True, string='Reserved')
    demanda = fields.Float(required=False, copy=False, readonly=True, string='SO Out')
    remanente = fields.Float(required=False, copy=False, readonly=True, string='Back Orders')
    compras = fields.Float(required=False, copy=False, readonly=True, string='PO Qty')
    compras_recibido = fields.Float(required=False, copy=False, readonly=True, string='PO Received Qty')
    compras_facturado = fields.Float(required=False, copy=False, readonly=True, string='PO Billed Qty')
    compras_total = fields.Float(required=False, copy=False, readonly=True, string='Purchase Total')
    pedidos_portal = fields.Float(required=False, copy=False, readonly=True, string='Portal Demand')
    entregado = fields.Float(required=False, copy=False, readonly=True, string='Delivered')
    facturado = fields.Float(required=False, copy=False, readonly=True, string='Invoiced')
    por_facturar = fields.Float(required=False, copy=False, readonly=True, string='Pending bill')
    diferencia = fields.Float(required=False, copy=False, readonly=True, string='Difference', help='Portal Order not purchased')
    
    def view_reserved_quantity(self):
        sml_ids = self.env['stock.move.line'].search([
                ('product_id','=',self.product_id.id),
                ('location_id','=',self.location_id.id),
                ('state','not in',['done','cancel']),
                ('product_qty','>',0)
                ])
        return self.env['stock.quant'].view_reserved_quantity_sml(sml_ids)

    def view_transit(self):
        lineas_ordenes = self.env['purchase.order.line'].search([
                ('company_id', '=', self.company_id.id),
                ('product_id', '=', self.product_id.id),
                ('create_date', '>', self.inventory_planning_config.fecha_inicio),
                ('state', 'in', ['purchase', 'done'])
                ])
        return self.env['purchase.order'].view_transit_sml(lineas_ordenes)
