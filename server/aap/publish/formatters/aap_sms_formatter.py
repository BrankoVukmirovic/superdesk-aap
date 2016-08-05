# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license
from eve.utils import ParsedRequest
from superdesk.publish.formatters import Formatter
from .aap_formatter_common import map_priority
from apps.archive.common import get_utc_schedule
import superdesk
from bs4 import BeautifulSoup
from superdesk.errors import FormatterError
from superdesk.metadata.item import ITEM_TYPE, CONTENT_TYPE, EMBARGO, CONTENT_STATE, ITEM_STATE
import json


class AAPSMSFormatter(Formatter):
    def format(self, article, subscriber, codes=None):
        """
        Constructs a dictionary that represents the parameters passed to the SMS InsertAlerts stored procedure
        :return: returns the sequence number of the subscriber and the constructed parameter dictionary
        """
        try:
            pub_seq_num = superdesk.get_resource_service('subscribers').generate_sequence_number(subscriber)
            sms_message = article.get('sms_message', article.get('headline', '')).replace('\'', '\'\'')

            # category = 1 is used to indicate a test message
            category = '1' if superdesk.app.config.get('TEST_SMS_OUTPUT', True) is True \
                else article.get('anpa_category', [{}])[0].get('qcode').upper()

            odbc_item = {'Sequence': pub_seq_num, 'Category': category,
                         'Headline': sms_message,
                         'Priority': map_priority(article.get('priority'))}

            body = self.append_body_footer(article)
            if article.get(EMBARGO):
                embargo = '{}{}'.format('Embargo Content. Timestamp: ',
                                        get_utc_schedule(article, EMBARGO).isoformat())
                body = embargo + body

            if article[ITEM_TYPE] == CONTENT_TYPE.TEXT:
                body = BeautifulSoup(body, "html.parser").text

            odbc_item['StoryText'] = body.replace('\'', '\'\'')  # @article_text
            odbc_item['ident'] = '0'

            return [(pub_seq_num, json.dumps(odbc_item))]
        except Exception as ex:
            raise FormatterError.AAPSMSFormatterError(ex, subscriber)

    def can_format(self, format_type, article):
        if format_type != 'AAP SMS' or article[ITEM_TYPE] != CONTENT_TYPE.TEXT \
                or article.get(ITEM_STATE, '') == CONTENT_STATE.KILLED \
                or not article.get('flags', {}).get('marked_for_sms', False):
            return False
        # need to check that a story with the same sms_message has not been published to SMS before
        query = {"query": {
            "filtered": {
                "filter": {
                    "and": [
                        {"term": {"state": CONTENT_STATE.PUBLISHED}},
                        {"term": {"sms_message": article.get('sms_message', article.get('headline', ''))}},
                        {"term": {"flags.marked_for_sms": True}},
                        {"not": {"term": {"queue_state": "in_progress"}}}
                    ]
                }
            }
        }
        }
        req = ParsedRequest()
        req.args = {'source': json.dumps(query)}
        published = superdesk.get_resource_service('published').get(req=req, lookup=None)
        if published and published.count():
            return False
        return article.get('flags', {}).get('marked_for_sms', False)
