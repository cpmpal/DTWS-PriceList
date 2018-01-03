#!/usr/bin/python

import fitz
from math import floor
import copy
from pylatex import Document, Tabular, MultiColumn, Section, Subsection, Description, Enumerate
from pylatex.utils import NoEscape
from pylatex.base_classes import Environment
from pylatex.package import Package
from datetime import date
import sys, os, subprocess
import re
import json
from decimal import *
from pprint import pprint

#tweak for pdf pixel sensitivity
DELTA = Decimal('2')
listName = ''

def withinOff(current, test):
	current = Decimal('%.3f' % current)
	test = Decimal('%.3f' % test)
	testLeft = current <= test + DELTA
	testRight = current >= test -DELTA
	return testLeft and testRight
	


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

	#Check if bbox is a single line or part of multiple lines
	def isSingleBbox(self, bbox):	
		s = bbox[u'lines'][-1][u'spans'] 
		return len(s) >= 4 and withinOff(s[-4][u'bbox'][0], Decimal('592.323'))

	# Big helper class for bbox functions to check offsets and contents
	class bboxMajor:
		
		barcodeOff = Decimal('24.5999')
		breweryOff = Decimal('109.515')
		beerOff = Decimal('199.221')
		sizeOff = Decimal('341.312')

		
		def fullSpan(self):
			for l in self.lines:
				for text in l.spans:
					self.span.append(text)
			self.size = len(self.span)
		
		def fullLine(self):
			full = []
			for b in self.span:
				full.append(b.text)
			return full
		
		def hasBarcode(self):
			return withinOff(self.span[0].xOffLeft, self.barcodeOff)
		def hasBrewery(self):
			return withinOff(self.span[1].xOffLeft, self.breweryOff)
		def hasBeer(self):
			return withinOff(self.span[2].xOffLeft, self.beerOff)
		def hasSize(self):
			if len(self.span) > 12:
				i = len(self.span) - 12 + 3
			else:
				i = 3
			if len(self.span) <= 4: return False
			#print(i, withinOff(self.span[i].xOffLeft, self.sizeOff))
			return withinOff(self.span[i].xOffLeft, self.sizeOff)
		
		def addBox(self, boxes):
			bb = dtwsPriceScraper.bboxMajor(boxes)
			once = False
			for b in self.span:
				if withinOff(b.xOffLeft, self.breweryOff) and not once:
					b.text = ';'+b.text
					once = True
			#pprint(bb.span)
			self.span[-1].text += ';'
			self.span.extend(bb.span)
			self.size = len(self.span)
			#print self.size
			
		def splitBrewery(self):
			bboxNew = copy.deepcopy(self.span[0])
			bboxNew.text = bboxNew.text.split(' ')[1]
			#print(bboxNew.text)
			bboxNew.xOffLeft = self.breweryOff
			self.span[0].text = self.span[0].text.split(' ')[0]
			self.span.insert(1, bboxNew)
			#raw_input("test")
		
		def splitSize(self):
			sz = re.compile('([0-9]{1,3}\.{0,1}[0-9]{1,2} ?[ozmlOZML]{1,3})')
			bboxNew = None
			for b in self.span:
				#print b.xOffLeft
				if withinOff(b.xOffLeft, self.beerOff):
					bboxNew = copy.deepcopy(b)
					#print bboxNew.text
			#print 'shit'
			#print bboxNew
			bboxNew.text = sz.split(bboxNew.text)[1]
			bboxNew.xOffLeft = self.sizeOff
			self.span[2].text = sz.split(self.span[2].text)[0]
			self.span.insert(3, bboxNew)	

		def __repr__(self):
			b = ''
			b += 'xL:'+str(self.xOffLeft)+'\n'
			b += 'yU:'+str(self.yOffUp)+'\n'
			b += 'yD:'+str(self.yOffDown)+'\n'
			b += 'xR:'+str(self.xOffRight)+'\n'
			if self.lines:
				for l in self.lines:
					b += '----------\n'
					b += l.__repr__()
			elif self.spans:
				for s in self.spans:
					b += '==========\n'
					b += s.__repr__()
			else:
				b += 'text: '+self.text + '\n'
			return b

		def __init__(self, box):
			self.xOffLeft = Decimal('%.3f' % box[u'bbox'][0])
			self.yOffUp = Decimal('%.3f' % box[u'bbox'][1])
			self.yOffDown = Decimal('%.3f' % box[u'bbox'][2])
			self.xOffRight = Decimal('%.3f' % box[u'bbox'][3])
			self.lines = []
			self.spans = []
			self.text = ''
			self.size = -1
			self.span = []
			if u'lines' in box:
				for b in box[u'lines']:
					self.lines.append(dtwsPriceScraper.bboxMajor(b))
			if u'spans' in box:
				for b in box[u'spans']:
					self.spans.append(dtwsPriceScraper.bboxMajor(b))
			if u'text' in box: 
				self.text = box[u'text']
			self.fullSpan()


	#Helper method to scrape out relevant text from json
	def cleanBBox(self, bbox):
		lines = []
		#pprint(bbox)
		#raw_input("raw bbox")
		currBox = self.bboxMajor(bbox[0])
		#pprint(currBox)
		#print currBox.fullLine()
		#pprint(currBox.span)
		#raw_input('full bbox')
		addBoxCalled = False
		if not currBox.hasBeer() and len(currBox.span) <= 4:
			currBox.addBox(bbox[1])
			addBoxCalled = True
		b = currBox
		#pprint(b.span)
		#raw_input("test")
		#LiquorPOS wraps bewery name, so only barcode/brewery and product/size
		#can become intermingled
		if not b.hasBarcode():
			return -1
		if not b.hasBrewery():
			b.splitBrewery()
		if not b.hasSize():
			b.splitSize()
		if not addBoxCalled:
			b.span[1].text = ';'+b.span[1].text+';'
		return b.fullLine()

	#Regex product info for name, size, quantity and price
	def productInfo(self, productLine):
		prog = re.compile('; ([0-9\w \W]+) ([0-9]{1,3}\.{0,1}[0-9]{1,2} [ozmlOZML]{1,2}) ([1246]{1,3}) ([0-9]{1,3}.[0-9]{2})')
		info = prog.match(productLine)
		if info is None:
			return None
			print "Could not match product:"
			print productLine
		return info.groups()

	#Create array of the product lines
	def getProducts(self):
		productLine = ''
		twoLine = False
		for page in self.json:
			productsBlob = page[u'blocks'][3:]
			boxes = []
			for bbox in productsBlob:
				boxes.append(bbox)
				#pprint(boxes)
				if not self.isSingleBbox(bbox):	
					continue
				else:
					line = self.cleanBBox(boxes)
					productLine+=' '.join(line)+' '
					self.products.append(productLine[:-1])
					boxes = []
					productLine = ''	
	#Print products
	def printProducts(self):
		print "============================="
		print "    FORMATTED DICTIONARY     "
		print "============================="
		pprint(self.productTable)

	#Create dictionary of breweries with products as list of product dictionaries per brewery
	#ex. { Brewery : [ {Beer 1},
	#		   {Beer 2}, ...]
	#				}
	def createProductDict(self):
		print "============================="
		print "         RAW PRODUCTS        "
		print "============================="
		for product in self.products:
			newProduct = {}
			try:
				print(product)
				#raw_input("prod")
				brandL = product.index(';')+1
				brandH = product.index(';', brandL+1)
				currentBrand = product[brandL:brandH]
				info = self.productInfo(product[brandH:])
				if info is None:
					print("Could not find match post cleaning: ")
					print product
					#raw_input("wtf")
					continue
				if not info:
					print("Could not find match post cleaning: ")
					print info
					print product
					#raw_input("false")
					continue
				else:
					newProduct['brewery'] = currentBrand.capitalize()
					#truncate product name for ease of formatting
					name = info[0].capitalize()
					'''
					if len(info[0]) > 16:
						name = info[0][:15]+u'\u2026'
						name = name.capitalize()
					'''
					newProduct['product'] = name
					newProduct['size'] = info[1]
					newProduct['pack'] = info[2]
					price = float(info[3])
					price += 0.05*int(info[2])
					price = str(price)
					newProduct['price'] = price
					if newProduct['brewery'] not in self.productTable:
						self.productTable[newProduct['brewery']] = [newProduct]
						#print("new brew")
					else:
						self.productTable[newProduct['brewery']].append(newProduct)
						#print("append brew")
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

	def productNameWrapped(self, prod):
		name = prod
		if len(name) > 18:
			if len(name) >= 16*2:
				name[32:]=u'\u2026'
			return name
				
		else:
			return name

	def makeDoc(self, craftBeerDict):
		self.document = Document(documentclass=self.documentclass, document_toptions=self.document_options, font_size=self.font_size, page_numbers=self.page_numbers, inputenc=self.inputenc, geometry_options=self.geometry_options, data=self.data)
		
		# Force enumitem package into document to change list seperation values
		self.document.packages.add(NoEscape('\usepackage{enumitem}'))
		self.document.packages.add(NoEscape('\usepackage[T1]{fontenc}'))
		self.document.packages.add(NoEscape('\usepackage{nimbussans}'))
		self.document.packages.add(NoEscape('\usepackage[table]{xcolor}'))
		self.document.packages.add(NoEscape('\usepackage{hanging}'))
		self.document._propagate_packages()
		self.document.append(NoEscape('\setlist{nosep}'))
		self.document.append(NoEscape('\setlength{\columnseprule}{0.5pt}'))
		self.document.append(NoEscape('\setlength{\columnsep}{1cm}'))
		self.document.append(NoEscape('\\renewcommand{\\familydefault}{\sfdefault}'))
		self.document.append(NoEscape('\sffamily'))
		self.document.append(NoEscape('\definecolor{lightgray}{gray}{0.9}'))
		self.document.append(NoEscape('\\rowcolors{1}{}{lightgray}'))
		with self.document.create(self.MultiCol(arguments='3')):
			self.document.append(Section(NoEscape('\\fontfamily{fvm}\selectfont '+listName), numbering=False))
			for brewery in craftBeerDict.keys():
				with self.document.create(Subsection(brewery, numbering=False)):
					with self.document.create(Tabular(NoEscape('>{\\raggedright}p{16ex\hangindent=3ex} c r'))) as brewTable:

						for beer in craftBeerDict[brewery]:
							brewTable.add_row([self.productNameWrapped(beer['product']), beer['size']+' x '+beer['pack'], beer['price']])
		print "Making price list..."
		self.document.generate_pdf(self.pdfName, clean=True, clean_tex=False, silent=True)
		#print os.getcwd()+'/'+self.pdfName+".pdf"
		subprocess.call(["xdg-open", os.getcwd()+'/'+self.pdfName+".pdf"])



if __name__ == '__main__':
	if len(sys.argv) > 3:
		listName = sys.argv[3]
	else:
		listName = "Craft Beer List "+listDate()

	if len(sys.argv) > 2:
		pdfName = sys.argv[2]
	else:
		pdfName = "craft-beer-list-"+listDate().replace('/', '-')

	if len(sys.argv) > 1:
		xpsFile = sys.argv[1]
	else:
		xpfFile = 'PryceList-TestFile-2.xps'

	test = dtwsPriceScraper(xpsFile)
	test.printProducts()

	textTest = priceList(pdfName)
	textTest.makeDoc(test.productTable)

