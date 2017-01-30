#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import logging
import argparse

from mongoengine import Q
from pandas import DataFrame

from logger import setup_logging
from models import StockInfo, QuantResult as QR, StockDailyTrading as SDT
from analysis.technical_analysis_util import calculate_ma, format_trading_data, check_duplicate_strategy
from analysis.technical_analysis_util import start_quant_analysis


query_step = 100  # 一次从数据库中取出的数据量


def quant_stock(stock_number, stock_name, **kwargs):
    short_ma = kwargs['short_ma']
    long_ma = kwargs['long_ma']
    qr_date = kwargs['qr_date']
    if short_ma <= long_ma:
        strategy_direction = 'long'
        quant_count = long_ma + 5
    else:
        strategy_direction = 'short'
        quant_count = short_ma + 5
    strategy_name = 'ma_%s_%s_%s' % (strategy_direction, short_ma, long_ma)

    sdt = SDT.objects(Q(stock_number=stock_number) & Q(today_closing_price__ne=0.0) &
                      Q(date__lte=qr_date)).order_by('-date')[:quant_count]
    if len(sdt) < quant_count:
        # trading data not enough
        return
    if float(sdt[0].increase_rate.replace('%', '')) > 9:
        return

    trading_data = format_trading_data(sdt)
    if not trading_data:
        return

    df = calculate_ma(DataFrame(trading_data), short_ma, long_ma)
    today_ma = df.iloc[-1]
    yestoday_ma = df.iloc[-2]

    if today_ma['diff_ma'] > 0 > yestoday_ma['diff_ma']:
        qr = QR(
            stock_number=stock_number, stock_name=stock_name, date=today_ma.name,
            strategy_direction=strategy_direction, strategy_name=strategy_name,
            init_price=today_ma['close_price']
        )
        if not check_duplicate_strategy(qr):
            qr.save()


def setup_argparse():
    parser = argparse.ArgumentParser(description=u'根据长短均线的金叉来选股')
    parser.add_argument(u'-s', action=u'store', dest='short_ma', required=True, help=u'短期均线数')
    parser.add_argument(u'-l', action=u'store', dest='long_ma', required=True, help=u'长期均线数')
    parser.add_argument(u'-t', action=u'store', dest='qr_date', required=False, help=u'计算均线的日期')

    args = parser.parse_args()

    if args.qr_date:
        try:
            qr_date = datetime.datetime.strptime(args.qr_date, '%Y-%m-%d')
        except Exception, e:
            print 'Wrong date form'
            raise e
    else:
        qr_date = datetime.date.today()

    return int(args.short_ma), int(args.long_ma), qr_date


if __name__ == '__main__':
    setup_logging(__file__, logging.WARNING)
    short_ma, long_ma, qr_date = setup_argparse()
    start_quant_analysis(short_ma=short_ma, long_ma=long_ma, qr_date=qr_date, quant_stock=quant_stock)
