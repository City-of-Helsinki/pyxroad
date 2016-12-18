import datetime
import uuid
from zeep import Client as ZeepClient, Plugin, exceptions as zeep_exceptions

_header = None


class XRoadPlugin(Plugin):
    def __init__(self, xroad_client):
        self.xroad_client = xroad_client

    def ingress(self, envelope, http_headers, operation):
        header = envelope.find('{http://schemas.xmlsoap.org/soap/envelope/}Header')
        remove_elements = ['requestHash', 'protocolVersion', 'issue']
        for el_name in remove_elements:
            el = header.find('{http://x-road.eu/xsd/xroad.xsd}%s' % el_name)
            if el is not None:
                header.remove(el)
        # print(etree.tostring(envelope, pretty_print=True).decode('utf8'))
        return envelope, http_headers

    def egress(self, envelope, http_headers, operation, binding_options):
        # Set serviceCode based on the SOAP request
        header = envelope.find('{http://schemas.xmlsoap.org/soap/envelope/}Header')

        el = header.find('{http://x-road.eu/xsd/xroad.xsd}id')
        el.text = uuid.uuid4().hex

        service = header.find('{http://x-road.eu/xsd/xroad.xsd}service')
        el = service.find('{http://x-road.eu/xsd/identifiers}serviceCode')
        el.text = operation.name

        # For some reason, zeep insists on adding WSA elements to the
        # header. This will only confuse some servers, so remove the
        # elements here.
        for el in header.getchildren():
            if el.prefix == 'wsa':
                header.remove(el)

        binding_options['address'] = self.xroad_client.security_server_url
        # print(etree.tostring(envelope, pretty_print=True).decode('utf8'))
        return envelope, http_headers


class XRoadClient(ZeepClient):
    def _set_default_headers(self):
        addr_fields = ('xRoadInstance', 'memberClass', 'memberCode', 'subsystemCode')
        service = {addr_fields[i]: val for i, val in enumerate(self.service_addr.split('.'))}
        service['serviceVersion'] = 'v1'
        service['objectType'] = 'SERVICE'
        # service['serviceCode'] = 'GetCompany'
        headers = {
            'client': {
                'xRoadInstance': self.xroad_instance,
                'memberClass': self.member_class,
                'memberCode': self.member_code,
                'subsystemCode': self.subsystem_code,
                'objectType': 'SUBSYSTEM'
            },
            'service': service,
            'userId': self.user_id,
            'protocolVersion': '4.0',
        }
        self.set_default_soapheaders(headers)

    def __init__(self, wsdl, security_server_url, client_addr, service_addr,
                 user_id, *args, **kwargs):
        self.security_server_url = security_server_url
        self.user_id = user_id
        self.xroad_instance = service_addr.split('.')[0]

        self.service_addr = service_addr
        assert len(service_addr.split('.')) == 4, "Service address must be a well-formed XRoad address"

        # Set client address elements
        l = client_addr.split('.')
        (instance, self.member_class, self.member_code, self.subsystem_code) = l
        assert instance == self.xroad_instance, "Client and service instances must be the same"

        plugins = kwargs.get('plugins', [])
        plugins.append(XRoadPlugin(self))
        kwargs['plugins'] = plugins
        super().__init__(wsdl, *args, **kwargs)

        self.set_ns_prefix('xrd', 'http://x-road.eu/xsd/xroad.xsd')
        self.set_ns_prefix('id', 'http://x-road.eu/xsd/identifiers')
        self._set_default_headers()


security_server_url = 'http://localhost:8088'
client_addr = 'FI-TEST.MUN.0201256-6.YTJclient'
client = XRoadClient('ytj.wsdl', security_server_url,
                     client_addr, 'FI-TEST.GOV.0244683-1.xroadytj-services',
                     user_id='test')
# client = XRoadClient('test-service.wsdl', security_server_url,
#                     client_addr, 'FI-TEST.GOV.0245437-2.TestService',
#                     user_id='test')


def get_company_info(business_id):
    req = {
        'companyQuery': {
            'BusinessId': business_id
        }
    }
    ret = client.service.GetCompany(request=req)
    info = ret['body']['response']['GetCompanyResult']['Company']

    req = {
        'taxDebtQuery': {
            'BusinessId': business_id
        }
    }
    try:
        ret = client.service.GetCompanyTaxDebt(request=req)
        tax_debt = ret['body']['response']['GetCompanyTaxDebtResult']['TaxDebt']
        info['TaxDebt'] = tax_debt
    except zeep_exceptions.Fault:
        tax_debt = {}
    return info

if 1:
    start = datetime.datetime(2016, 10, 12)
    req = {
        'updatedCompaniesQuery': {
            'StartDate': start
        }
    }
    if 0:
        ret = client.service.GetUpdatedCompanies(request=req)
        res = ret['body']['response']['GetUpdatedCompaniesResult']['UpdatedCompanies']['UpdatedCompaniesQueryResult']
        business_ids = [x['BusinessId'] for x in res]
        print(business_ids)
        bid = business_ids[0]
    else:
        bid = '0244683-1'
    print("Getting information on %s" % bid)
    print(get_company_info(bid))


if 0:
    ret = client.service.getRandom()
    print(ret)
