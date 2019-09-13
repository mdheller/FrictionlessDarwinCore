from FrictionlessDarwinCore import DwCVocabulary
import xml.etree.ElementTree as ET
import re
import json

class DwCStructure:
    voc = DwCVocabulary()
    ns = {'dwc': 'http://rs.tdwg.org/dwc/text/'}

    def __init__(self, meta, eml):
        self.eml = eml
        self.meta = meta
        self.descriptor = {}
        self.corename=''
        self.valid=False

    def convert(self):
        # convert meta.xml into datapackage descriptor
        self.descriptor = {}
        if self.eml != None:
            dataset = ET.fromstring(self.eml).find('./dataset')
            self._addheader(dataset)
        if self.meta != None:
            archive = ET.fromstring(self.meta)
            resources = []
            core=archive.find('dwc:core', DwCStructure.ns)
            self.corename=core.get('rowType').rsplit('/', 1)[1].lower()

            resources.append(self._toresource(core, True))
            for extension in archive.findall('dwc:extension', DwCStructure.ns):
                resources.append(self._toresource(extension, False))
            self._add('resources', resources)
        self.valid=True
        return self.as_json()


    def as_json(self):
        return json.dumps(self.descriptor)

    def _add(self, key, value):
        self.descriptor[key]=value


    def _addheader(self, dataset):
        licences = []
        sources = []
        for ai in dataset.findall('./alternateIdentifier'):
            m=re.search(r'(?<==)\w+', ai.text)
            if m != None:
                self._add('name',m.group(0))
            if re.search('^[0-9a-f\-]*$',ai.text) !=None:
                self._add('id',ai.text)
            if re.search('^https?://', ai.text) !=None:
                source = {}
                source['title'] = 'GBIF IPT'
                source['path'] = ai.text
                sources.append(source)
        self._add('title', dataset.findtext('./title'))
        self._add('profile','tabular-data-package')
        ipr= dataset.find('./intellectualRights')
        if ipr != None:
            licence={}
            title=ipr.findtext('./para/ulink/citetitle')
            if re.search('\((.+)\)',title):
                licence['name']=re.search('\((.+)\)',title).group(0)
            licence['path']=ipr.find('./para/ulink').get('url')
            licence['title']=title
            licences.append(licence)
        self._add('licences', licences)

        self._add('sources', sources)

    def _delimiter(self, delimiterString):
        switcher = {
            "":'"',
            "\\n": '\n',
            "\\r": '\r',
            "\\r\\n": '\r\n',
            "\\t": '\t',
        }
        return switcher.get(delimiterString, delimiterString)

    def _toresource(self, mfile, core):
        if mfile is None:
            return
        r = {}
        files= mfile.find('dwc:files', DwCStructure.ns)
        location= files.find('dwc:location', DwCStructure.ns)
        r['name']= location.text.split('.')[0]
        r['path']= location.text
        r['profile']='tabular-data-resource'
        r['encoding']=mfile.get('encoding')
        r['format']= 'csv'
        dialect={}
        dialect['csvddfVersion']=1.2
        dialect['delimiter']= self._delimiter(mfile.get('fieldsTerminatedBy'))
        dialect['doubleQuote']=True
        dialect['lineTerminator']= self._delimiter(mfile.get('linesTerminatedBy'))
        dialect['quoteChar']= self._delimiter(mfile.get('fieldsEnclosedBy'))
        dialect['skipInitialSpace']=True
        dialect['header']= mfile.get('ignoreHeaderLines')=='1'
        dialect['commentChar']='#'
        r['dialect']=dialect

        schema= {}
        fields= []
        need_additional_id_field=True
        for f in mfile.findall('dwc:field', DwCStructure.ns):
            if f.get('index')=="0":
                need_additional_id_field = False

        if need_additional_id_field:
            print('Adding addtional_id_field')
            field = {}
            field['name']='id'
            field['type'] = 'string'
            field['format'] = 'default'
            fields.append(field)

        for f in mfile.findall('dwc:field', DwCStructure.ns):
            field= {}
            mterm=f.get('term')
            term = self.voc.term(mterm)
            if term == None:
                print(mterm, 'unkwown Darwin Core term.')
                field['name'] = mterm.rsplit('/', 1)[1]
                field['type'] = 'string'
            else:
                field['name'] = term['name']
                field['type'] = term['type']
                field['description'] = mterm
                if term['format'] != 'default':
                    field['format']= term['format']
                if term['constraints'] != '':
                    field['constraints'] = json.loads(term['constraints'])
            fields.append(field)
        schema['fields']= fields
        r['schema']= schema
        if core:
            r['primaryKey']='id'
        else:
            fkeys= []
            fkey= {}
            fkey['fields']='id'
            ref={}
            ref['resource']=self.corename
            ref['fields']='id'
            fkey['reference']=ref
            fkeys.append(fkey)
            r['foreignKeys']=fkeys
        return r
