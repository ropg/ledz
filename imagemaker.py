#!/usr/bin/python

from __future__ import division # So "/" operator always returns a float, as it will be in Python 3
import Image,  math, re

def imagemaker( (width, height) , color):
	part = re.split('\(|\)|,', color) + ['','','','']
	if part[0] == 'rainbow':	
		if part[1]:
			rainbowwidth = int(part[1])
		else:
			rainbowwidth = 60
		if part[2]:
			angle = int(part[2])
		else:
			angle = 45

		img = Image.new( "RGB", (width, height), (0,0,0) )
		for x in xrange (width):
			for y in xrange (height):
				# offset is set to a float between 0 ad 1 for where we are in the rainbow
				# ( math.modf(x) returns the fractional and integer part of a float as two floats)
				offset = math.sin(math.radians(angle)) * x + math.cos(math.radians(angle)) * y
				offset = math.modf( offset / rainbowwidth)[0]
				
				# stage is which of the six stages we're in, phase is the position within that stage
				phase, stage = math.modf(offset * 6)
				stage = int(stage)
				rising = int( phase * 256 )
				falling = 255 - rising
				
				# Each stage is characterized as follows
				if stage is 0:
					red = 255; green = rising; blue = 0
				if stage is 1:
					red = falling; green = 255; blue = 0
				if stage is 2:
					red = 0; green = 255; blue = rising
				if stage is 3:
					red = 0; green = falling; blue = 255
				if stage is 4:
					red = rising; green = 0; blue = 255
				if stage is 5:
					red = 255; green = 0; blue = falling
				
				img.putpixel( (x, y), (red, green, blue) )	
	
	else:
		img = Image.new ( "RGB", (width, height), color)

	return img