#!/usr/bin/python

import fitz
import sys, os
import re
import json
from pprint import pprint

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
		return lines

	#Regex product info for name, size, quantity and price
	def productInfo(self, productLine):
		print productLine
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
				print(line)
				if not line[0][0].isdigit():
					productLine+=' '.join(line)+' '
					self.products.append(productLine[:-1])
					productLine=''
				else:	
					line[1] = ';'+line[1]
					if line[-1][-1].isdigit():
						line[1] = line[1]+';'
					else:
						line[-1] = line[-1]+';'
					productLine+=' '.join(line)+' '
					
		pprint(self.products)

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
					newProduct['price'] = info[3]
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
		#self.createProductDict()		

test = dtwsPriceScraper('PryceList-TestFile-2.xps')
#test.printProducts()