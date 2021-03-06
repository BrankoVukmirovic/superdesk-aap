# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014, 2015, 2016, 2017 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import re

from superdesk.io.feed_parsers import NewsMLTwoFeedParser
from superdesk.io.feed_parsers.newsml_2_0 import NS, NITF
from superdesk.io.registry import register_feed_parser, register_feeding_service_parser
from apps.io.feeding_services.reuters import ReutersHTTPFeedingService
from superdesk.metadata.item import CONTENT_TYPE
from aap.utils import DATELINE_REGEX


class ReutersNewsMLTwoFeedParser(NewsMLTwoFeedParser):
    """
    Feed Parser which can parse if the feed is in NewsML 2 format.

    """

    NAME = 'reutersnewsml2'
    label = 'Reuters News ML 2.0 Parser'

    def parse_content_place(self, tree, item):
        """Parse subject with type="cptType:5" into place list."""
        item['place'] = []

    def parse_inline_content(self, tree, item, ns=NS['xhtml']):
        if tree.get('contenttype') == NITF:
            return super().parse_inline_content(tree, item, ns)
        else:
            html = tree.find(self.qname('html', ns))
            body = html.find(self.qname('body', ns))
            elements = []
            # Some content is receievd as a single p tag
            if len(body.findall(self.qname('p', ns))) == 1 and body[0].tag.rsplit('}')[1] == 'p':
                elem = body[0]
                if elem.text:
                    tag = elem.tag.rsplit('}')[1]
                    elements.append(
                        '<%s>%s</%s>' % (tag, elem.text.replace('\n    ', '</p><p>').replace('\n', '<br/>'), tag))
            else:
                dateline_found = None
                line_counter = 0
                for elem in body:
                    if not elem.text:
                        continue

                    byline_found = False
                    tag = elem.tag.rsplit('}')[1]
                    elem_text = elem.text.replace('\n', ' ')
                    # look for byline and dateline in first 10 lines
                    if line_counter < 10:
                        if not dateline_found:
                            dateline_found = re.search(DATELINE_REGEX, elem_text, re.IGNORECASE | re.MULTILINE)

                        if not dateline_found:
                            byline = item.get('byline') or ''
                            if byline:
                                byline_prefix = ''
                                if not byline.startswith('By '):
                                    byline_prefix = 'By '
                                byline_found = elem_text.lower().startswith('{}{}'.format(byline_prefix,
                                                                                          byline).lower())
                            else:
                                byline_found = elem_text.startswith('By ')
                                if byline_found:
                                    item['byline'] = elem_text

                    # remove the byline from the body text
                    if not byline_found:
                        elements.append('<%s>%s</%s>' % (tag, elem_text, tag))

                    line_counter += 1

            content = dict()
            content['contenttype'] = tree.attrib['contenttype']
            if len(elements) > 0:
                content['content'] = "\n".join(elements)
            elif body.text:
                content['content'] = '<pre>' + body.text + '</pre>'
                content['format'] = CONTENT_TYPE.PREFORMATTED
            return content


register_feed_parser(ReutersNewsMLTwoFeedParser.NAME, ReutersNewsMLTwoFeedParser())
register_feeding_service_parser(ReutersHTTPFeedingService.NAME, ReutersNewsMLTwoFeedParser.NAME)
