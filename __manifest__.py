# -*- coding: utf-8 -*-

{
    'name': 'Planeación y manejo de inventario',
    'version': '12.0.1.0.1',
    'summary': 'Manejo y planeación de inventarios',
    'author': 'Julio Ramírez R.',
    'license': 'AGPL-3',
    'company': 'FacturaOdooCR.com',
    'website': 'https://facturaodoocr.com',
    'maintainer': 'FacturaOdooCR.com',
    'category': 'Inventory',
    'depends': ['stock'],
    'data': [
          'views/inventory_planning.xml',
          'views/product_view.xml',
          'views/menu_views.xml',
          'security/warehouse_security.xml',
          'security/ir.model.access.csv'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}

