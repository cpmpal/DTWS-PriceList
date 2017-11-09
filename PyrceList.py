#!/usr/bin/python

import fitz
from pylatex import Document, Tabular, MultiColumn, Section, Subsection, Description, Enumerate
from pylatex.utils import NoEscape
from pylatex.base_classes import Environment
from pylatex.package import Package
from datetime import date
import sys, os
import re
import json
from pprint import pprint

# quick wrapper to get the current date string
def listDate():
	dat = date.today()
	return(str(dat.month) + '/' + str(dat.day))

class dtwsPriceScraper:
	
	#Scrape xps into formatted json
	def convertToJSON(self):
		doc = fitz.open(self.xps)
		for page in range(doc.pageCount):
			jsonBlob = ''
			p = doc[page]
			jsonBlob = p.getText('json')
			self.json.append(json.loads(jsonBlob))

	#Helper method to scrape out relevant text from json
	def cleanBBox(self, bbox):
		bboxLines = bbox[u'lines']
		lines = []
		for i in bboxLines:
			for j in i[u'spans']:
				lines.append(j[u'text'])
		

		#check for barcode swallowing brewery
		if not lines[0][-1].isdigit() and lines[0][0].isdigit():
			try:
				start = lines[0].index(' ')+1
				lines.insert(1, lines[0][start:])
				lines[0] = lines[0][0:start-1]
			except ValueError:
				pass
			
		return lines

	#Regex product info for name, size, quantity and price
	def productInfo(self, productLine):
		prog = re.compile('; ([\w \W]+) ([0-9]{1,3} [ozml]{1,3}) (1|4|6) ([0-9]{1,3}.[0-9]{2})')
		info = prog.match(productLine)
		return info.groups()

	#Create array of the product lines
	def getProducts(self):
		productLine = ''
		for page in self.json:
			productsBlob = page[u'blocks'][3:]
			for bbox in productsBlob:
				line = self.cleanBBox(bbox)
				if not line[0][0].isdigit():
					productLine+=' '.join(line)+' '
					self.products.append(productLine[:-1])
					productLine=''
				else:	
					line[1] = ';'+line[1]
					if line[-1][-1].isdigit():
						line[1] = line[1]+';'
						productLine = ' '.join(line)
						self.products.append(productLine)
						productLine=''
					else:
						line[-1] = line[-1]+';'
						productLine+= ' '.join(line)+' '


	#Print products
	def printProducts(self):
		pprint(self.productTable)

	#Create dictionary of breweries with products as list of product dictionaries per brewery
	#ex. { Brewery : [ {Beer 1},
	#		   {Beer 2}, ...]
	#				}
	def createProductDict(self):
		for product in self.products:
			newProduct = {}
			try:
				brandL = product.index(';')+1
				brandH = product.index(';', brandL+1)
				currentBrand = product[brandL:brandH]
				info = self.productInfo(product[brandH:])
				if info is None:
					print product
					continue
				if not info:
					continue
				else:
					newProduct['brewery'] = currentBrand.capitalize()
					newProduct['product'] = info[0].capitalize()
					newProduct['size'] = info[1]
					newProduct['pack'] = info[2]
					price = float(info[3])
					price += 0.05*int(info[2])
					price = str(price)
					newProduct['price'] = price
					if newProduct['brewery'] not in self.productTable:
						self.productTable[newProduct['brewery']] = [newProduct]
					else:
						self.productTable[newProduct['brewery']].append(newProduct)

			except ValueError:
				continue

	'''
	XPS is the xps file exported from POS
	json is the extracted json from the XPS file
	products is the cleaned list of products and corresponding prices
	'''
	def __init__(self, xps):
		self.xps = xps
		self.json = []
		self.products = []
		self.productTable = {}
		self.convertToJSON()
		self.getProducts()
		self.createProductDict()		


class priceList:

	class MultiCol(Environment):

		packages = [Package('multicol')]
		escape = False
		content_seperator = "\n"
		_latex_name = 'multicols'
	
	def __init__(self, pdfName='full'):
		self.geometry_options = ["margin=0.25in", "portrait"]
		self.document_options = ""
		self.font_size = 'normalsize'
		self.documentclass = "article"
		self.inputenc = "utf8"
		self.page_numbers = False
		self.data = None
		self.document = None
		self.pdfName = pdfName	

	def makeDoc(self, craftBeerDict):
		self.document = Document(documentclass=self.documentclass, document_toptions=self.document_options, font_size=self.font_size, page_numbers=self.page_numbers, inputenc=self.inputenc, geometry_options=self.geometry_options, data=self.data)
		
		# Force enumitem package into document to change list seperation values
		self.document.packages.add(NoEscape('\usepackage{enumitem}'))
		self.document.packages.add(NoEscape('\usepackage[T1]{fontenc}'))
		self.document.packages.add(NoEscape('\usepackage{nimbussans}'))
		self.document._propagate_packages()
		self.document.append(NoEscape('\setlist{nosep}'))
		self.document.append(NoEscape('\setlength{\columnseprule}{0.5pt}'))
		self.document.append(NoEscape('\setlength{\columnsep}{1cm}'))
		self.document.append(NoEscape('\\renewcommand{\\familydefault}{\sfdefault}'))
		self.document.append(NoEscape('\sffamily'))

		with self.document.create(self.MultiCol(arguments='3')):
			self.document.append(Section(NoEscape('\\fontfamily{fvm}\selectfont Craft Beer List '+listDate()), numbering=False))
			for brewery in craftBeerDict.keys():
				with self.document.create(Subsection(brewery, numbering=False)):
					with self.document.create(Tabular('l c r')) as brewTable:

						for beer in craftBeerDict[brewery]:
							brewTable.add_row([beer['product'], beer['size']+' x '+beer['pack'], beer['price']])
	
		self.document.generate_pdf(self.pdfName, clean=True, clean_tex=False, silent=False)



if __name__ == '__main__':
	if len(sys.argv) > 1:
		pdfName = sys.argv[1]
	else:
		pdfName = "craft-beer-list-"+listDate().replace('/', '-')

	test = dtwsPriceScraper('PryceList-TestFile-2.xps')
	test.printProducts()

	textTest = priceList(pdfName)
	textTest.makeDoc(test.productTable)

