#!/usr/bin/python

'''

ledz.py can scroll text across a display made of a string of LEDs with LPD8806 controller
chips. Enter ./ledz.py -h for help. More information can be found at 

http://rop.gonggri.jp/

ledz by Rop Gonggrijp is licensed under a 
Creative Commons Attribution-ShareAlike 3.0 Unported License.

'''


from __future__ import division			# So / operator always returns a float
import argparse, time, signal, sys, os, math, subprocess, re
import Image, ImageDraw, ImageFont, ImageColor		# Python Image Library
from imagemaker import imagemaker						# Rop's own script in this directory

# global framesize, spidev

def CleanExit(signal, frame):
	print "Ctrl-C pressed, blanking screen"
	# Why the extra 9 bytes, I don't know...
	spidev.write('\x80' * (framesize + 9) +'\x00')
	spidev.flush()
	exit(0)

def PrintOut(string):
	sys.stderr.write(string + '\n')
	sys.stderr.flush()

# The following uses argparse to set args.variables for cli/configfile parameters
# See http://docs.python.org/2/library/argparse.html#module-argparse

# SpecialParse is an instance of argparse that can process 
# config files with option name and value on one line
class SpecialParse (argparse.ArgumentParser):
	def convert_arg_line_to_args(self, arg_line):
		if arg_line.strip() and arg_line[:1] != '#':
			if arg_line[:2] != '--':
				arg_line = '--' + arg_line
			for arg in arg_line.split():
				yield arg
			
parser = SpecialParse(
	description= 'Scrolling text on LED displays built with LPD8806-based adressable LED strips.', 
	fromfile_prefix_chars='@'
)
	
hardware = parser.add_argument_group('hardware', 'Describing the LED array hookup') 
hardware.add_argument('--width', 
	help='Number of LEDs per row.', 
	type=int, 
	metavar='<cols>',
	required=True)
hardware.add_argument('--height',
	help='Number of rows.',
	type=int,
	metavar='<rows>',
	required=True)
hardware.add_argument('--firstled',
	help='Position of the first LED on the screen',
	choices=['topleft', 'bottomleft', 'topright', 'bottomright'],
	metavar='<position>',
	default='topleft')
hardware.add_argument('--flippedrows',
	help='Manually override which a space separated list of rows that are placed backwards. Not needed if your rows are zig-zagging from the first led, which is the default.',
	type=int,
	nargs='*',
	metavar='row')
hardware.add_argument('--spidev',
	metavar='<device>',
	help='SPI device that LEDs are attached to. Defaults to /dev/spidev0.0',
	type=argparse.FileType('wb'),
	default='/dev/spidev0.0')
hardware.add_argument('--spispeed',
	help='Speed the spi port is operated at. Speeds from 200000 (200 KHz) to 32000000 (32 MHz) seem to work well with my LPD8806-based LED display. Slower speeds bring lower maximum refresh rates, obviously. defaults to 8 MHz',
	type=int,
	metavar='<bps>',
	default=8000000)
	
create = parser.add_argument_group('create', 'Creating text scroll')
create.add_argument('--virtual', '-v',
	help='Smoother scrolling by rendering on a virtual display that is this many times enlarged and then reduced with anti-aliasing.',
	default=1,
	type=int)
create.add_argument('--fontface',
	help='TrueType font to be used. Will look in fonts directory under current directory if no path is given.',
	default="ADDLG___.TTF")
create.add_argument('--fontsize',
	help='Size font will be rendered at',
	default=9)
create.add_argument('--fontbase',
	help='Vertical offset for font rendering as not all fonts have the same baseline. Positive or negative integer.',
	type=int,
	default=0)
create.add_argument('--foreground', '-f',
	help='Text foreground color, defaults to white. "#ff0000", "#f00", "rgb(255,0,0)", "rgb(100%%,0%%,0%%)", "hsl(0,100%%,50%%)", "red" and "Red" all specify pure red. (Your shell may force you to escape the # to \#). Use rainbow(200,45) to overlay a 200 (virtual screen) px wide rainbow slanted at 45 degrees.',
	metavar='<color>',
	default='white')
create.add_argument('--background', '-b',
	help='Text background color, defaults to black. Same rules as for foreground color apply.',
	metavar='<color>',
	default='black')
create.add_argument('--verticalsmooth',
	help='By default, the anti-aliasing smoothing is only done along the horizontal axis. Specify this option for fonts that look better when smoothed along vertical axis also.',
	action='store_true')
create.add_argument('--noleadin',
	help='Normally a movie starts with a blank screen and text scrolling in from the right. With noleadin the text is just there right away.',
	action='store_true')
create.add_argument('--noleadout',
	help='Normally a movie end on a blank screen after the text scrolled out on the left. With noleadout the movie ends with the last part of the text on the screen.',
	action='store_true')
create.add_argument('--compress',
	help='Compress the resulting bitmap horizontally, with factor specified. so 1.5 will make font 1.5 times narrower, 0.50 will stretch to twice the width.',
	type=float,
	metavar='<factor>',
	default=1)
create.add_argument('--text', '-t',
	help='Text to scroll. Enclose in singe quotes',
	metavar='\'text\'',
	default='TESTING ledz')
create.add_argument('--tobecontinued', '-c',
	help='Write intermediary canvas to continued.png in local directory and exit',
	action='store_true')
create.add_argument('--continued', '-C',
	help='Append new canvas to right of continued.png',
	action='store_true')
create.add_argument('--output', '-o',
	help='File to place the movie in. If this is provided, all arguments to do with displaying are ignored and program exits after saving movie',
	type=argparse.FileType('wb') )

play = parser.add_argument_group('play', 'Showing on the LED display')
play.add_argument('--input', '-i',
	help='File to read the movie from. If this is provided, all arguments to do with creating a movie are ignored.',
	type=argparse.FileType('rb'))
play.add_argument('--brightness',
	help='Brightness of clip, as a number between 0 and 1 for dimmer and larger than 1 for brighter. Note that clipping will occur.',
	type=float,
	default='1')
play.add_argument('--playcount', '-p',
	help='How many times to loop, defaults to indefinite looping.',
	type=int,
	default='0')
play.add_argument('--fps',
	help='Frames per second.',
	type=float)

conffile = 'ledz.conf'
# If default config file exists ...
if os.path.exists(conffile):
	# load its contents before command line options
	args = parser.parse_args( ['@' + conffile] + sys.argv[1:] )
else:
	# otherwise just parse command line arguments
	args = parser.parse_args()
	
# See if there is something to do
if args.input:
	if args.output:
		exit ("Cannot simultaneously read from movie file and write output to movie file, as this would only copy a file.")
else:		
	if not args.text:
		exit ("Either a text to be displayed or a movie to be played must be specified.")
	
	
# Set spi device speed
spidevfilename = re.search(r"open file '(.*?)'", str(args.spidev) ).group(1)
DEVNULL = open(os.devnull, 'wb')
ret = subprocess.call(["./spiset", "-D", spidevfilename, "-s", str(args.spispeed)], stdout=DEVNULL, stderr=DEVNULL)
if ret != 0:
	exit ("Could not set spi port {} to speed {}".format(spidevfilename, args.spispeed))

### Provide dynamic defaults and do sanity checks on arguments

# If we're writing a continuation PNG, we're leaving leadin and leadout
# to the instance that makes the actual movie
if args.tobecontinued:
	args.noleadin = True
	args.noleadout = True

# Calculate gamma correction table.	 This includes
# LPD8806-specific conversion (7-bit color w/high bit set).
gamma = bytearray(256)
for i in range(256):
	gamma[i] = 0x80 | int(pow(float(i) / 255.0, 2.5) * 127.0 + 0.5)

# Determine the order the lines are scanned in and which rows are flipped horizontally
if args.firstled == 'topleft':
	upsidedown = False; flippedrows = range(1, args.height, 2)
if args.firstled == 'topright':
	upsidedown = False; flippedrows = range(0, args.height, 2)
if args.firstled == 'bottomleft':
	upsidedown = True; flippedrows = range(1, args.height, 2)
if args.firstled == 'bottomright':
	upsidedown = True; flippedrows = range(0 , args.height, 2)

# Only use the flipped rows defined above if they're not manually overridden with --flippedrows 
if not args.flippedrows:
	args.flippedrows = flippedrows

# Create bytearray screen holding three bytes per pixel ( R, G and B byte per pixel)
framesize = args.width * args.height * 3
frame = bytearray(framesize)
movie = []

if args.input:
	PrintOut ('Reading from movie file')
	while True:
		frame = args.input.read(framesize)
		if len(frame) == 0:
			break
		movie.append(frame[:])

else:
	
	PrintOut ('Rendering image')
	
	# Get width of text in pixels using a temporary image
	font = ImageFont.truetype("fonts/" + args.fontface , args.fontsize * args.virtual)
	tmpimg = Image.new("L", (1,1), 0)
	tmpdraw = ImageDraw.Draw(tmpimg)
	textwidth = tmpdraw.textsize(args.text, font=font)[0]
	screenwidth = int ( args.width * args.virtual * args.compress )
	
	if args.continued:
		continued = Image.open("canvas.png")
		continuedwidth = continued.size[0]
	else:
		continuedwidth = 0
		
	if args.noleadin:
		leadin = 0
	else:
		leadin = screenwidth
	
	if args.noleadout:
		leadout = 0
	else:
		leadout = screenwidth
	
	# Determine width and height of image holding the text
	canvaswidth = leadin + continuedwidth + textwidth + leadout
	canvasheight = args.height * args.virtual
	
	# Create a monochrome image called mask and put the text on it
	mask = Image.new("L", ( canvaswidth, canvasheight ), 0)
	maskdraw = ImageDraw.Draw(mask)
	maskdraw.text( (leadin + continuedwidth , args.fontbase * args.virtual), args.text, (255), font=font)			
	
	# Create RGB background image
	background = imagemaker( ( canvaswidth, canvasheight ), args.background )
	
	# Create RGB foreground image
	foreground = imagemaker( ( canvaswidth, canvasheight ), args.foreground )
	
	# Mix foreground and background using text mask
	canvas = Image.composite(foreground, background, mask)
	
	if args.continued:
		PrintOut ("Appending to intermediary canvas")
		canvas.paste(continued, (leadin, 0, leadin+continuedwidth, canvasheight) )
	
	if args.tobecontinued:
		PrintOut ("Saving intermediary canvas")
		canvas.save ("canvas.png")
		exit(0)
	
	# Compress or expand
	if args.compress != 1:
		canvas = canvas.resize( ( int(canvaswidth / args.compress), canvasheight), Image.ANTIALIAS )
		canvaswidth = canvas.size[0]
		screenwidth = args.width * args.virtual
	
	PrintOut('Creating movie')
	
	if canvaswidth < screenwidth:
		canvaswidth = screenwidth + 1
	
	for scroll in xrange ( canvaswidth - screenwidth ):
		img = canvas.crop( (scroll, 0, scroll + (args.width * args.virtual) - 1 , canvasheight - 1) )
		img.load()
	
		if not args.verticalsmooth:
			img = img.resize( (args.width * args.virtual, args.height))
		img = img.resize( (args.width, args.height), Image.ANTIALIAS )
	
		pixels = img.load()
	
		for y in xrange (args.height):
			if y in args.flippedrows:
				flipped = True
			else:
				flipped = False
	
			if upsidedown:
				readrow = args.height - y - 1
			else:
				readrow = y
		
			for x in xrange (args.width):
				colors=pixels[x, readrow]
				x2 = x
				if flipped:
					x2 = args.width - x - 1
				offset = (y * args.width * 3 ) + (x2 * 3)
				frame[offset]	  = gamma[colors[1]]
				frame[offset + 1] = gamma[colors[0]]
				frame[offset + 2] = gamma[colors[2]]
	
		movie.append(frame[:])
		
if args.output:

	PrintOut('Saving movie')
	for x in xrange( len(movie) ):
		frame = movie[x]
		args.output.write(frame)
	args.output.close()

else:
	
	#Catch Ctrl-C
	signal.signal(signal.SIGINT, CleanExit)
	spidev = args.spidev
	
	# Set frames per second. If not provided, set to 20 fps, multiplied by the virtual screen factor.
	# (So a 4 times enlarged virtual screen (-- virtual 4) plays at 80 fps by default)
	if args.fps:
		fps = args.fps
	else:
		fps = 20 * args.virtual	
	
	# Calculate maximum fps at current screen size and spi device bitrate
	spidelay = framesize * 8 / args.spispeed
	maxfps = int ( 1 / spidelay )

	# Warn if fps higher than theoretical maximum and set for no delay
	if fps > maxfps:
		PrintOut("Warning: specified {} fps is faster than {} fps maximum at {} bps.".format(fps, maxfps, args.spispeed) )
		PrintOut("Displaying frames at maximum speed.")
		fps = maxfps
		delay = 0
	else:
		# Subtract time needed for data transfer from interframe delay
		delay = (1 / fps) - spidelay
		
	# Adjust brightness

	if args.brightness != 1:
		PrintOut("Adjusting brightness")
		for x in xrange( len(movie) ):
			frame = movie[x]
			for y in xrange( len(frame) ):
				value = int( ( frame[y] & 127 ) * args.brightness)
				if value > 127:
					value = 127
				frame[y] = value | 0x80
				

	PrintOut("Playing movie ({} fps)".format(fps))
	
	playcount = 0
	while True:
		for x in xrange( len(movie) ):
			frame = movie[x]
			spidev.write(frame + '\x00')
			spidev.flush()
			time.sleep(delay)
		playcount += 1
		if args.playcount == playcount:
			break 
