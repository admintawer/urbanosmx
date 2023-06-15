# -*- coding: utf-8 -*-
{
    'name': "Formato remision Urbanos",

    'summary': """
        Personalizacion formato recibo de entrega para remisiones""",

    'author': "Rail / Kevin Lopez",
    'website': "https://www.rail.com.mx",
    'category': 'Customization',
    'version': '0.1',
    'depends': ['stock', 'sale_stock'],
    'data': [
        'views/stock_picking.xml',
        'reports/delivery_order.xml',
    ],
}
