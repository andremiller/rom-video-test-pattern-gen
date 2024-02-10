import argparse
import os
from PIL import Image, ImageOps

# Configuration settings
ROM_CLOCK_FREQ = 2000000 # Hz
DISPLAY_TYPE = "PET12"

# Display configurations

DCONFIGS = {
    "PET9" : {
        "HORIZONTAL_FREQ" : 15625, # Hz
        "VERTICAL_FREQ" : 60, # Hz"
        "VERT_DRIVE_START_OFFSET" : -5, # Vertical drive starts 5us before start of frame
        "VERT_DRIVE_LINES" : 20, # Vertical drive is active for 20 lines at start of frame
        "HOR_DRIVE_DURATION" : 24, # Horizontal drive is 24us long at start of line
        "VID_START_OFFSET" : 18, # Video starts 18us after start of line
        "VID_DURATION" : 40, # Video is 40us long
        "VID_START_LINE" : 40, # Start video on horizontal line 40
        "VID_LINES" : 200, # Draw 200 video lines
    },
    "PET12" : {
        "HORIZONTAL_FREQ" : 20000, # Hz
        "VERTICAL_FREQ" : 50, # Hz"
        "VERT_DRIVE_START_OFFSET" : -5, # Vertical drive starts 5us before start of frame
        "VERT_DRIVE_LINES" : 16, # Vertical drive is active for 16 lines at start of frame
        "HOR_DRIVE_DURATION" : 24, # Horizontal drive is 24us long at start of line
        "VID_START_OFFSET" : 10, # Video starts 10us after start of line
        "VID_DURATION" : 40, # Video is 40us long
        "VID_START_LINE" : 80, # Start video on horizontal line 80
        "VID_LINES" : 240, # Draw 240 video lines
    },
}

# Calculated values
ROWS = int(DCONFIGS[DISPLAY_TYPE]["HORIZONTAL_FREQ"]/DCONFIGS[DISPLAY_TYPE]["VERTICAL_FREQ"])   # Number of lines per frame
HOR_TIME = 1000000 / DCONFIGS[DISPLAY_TYPE]["HORIZONTAL_FREQ"] # Time of horizontal line in us
HOR_RES = 1000000 / ROM_CLOCK_FREQ # Horizontal resolution in us
COLUMNS = int(HOR_TIME/HOR_RES)  # Number of columns

NAME=DISPLAY_TYPE+"_"+str(HOR_RES)+"us"

grid_array_vert  = [0] * COLUMNS * ROWS
grid_array_horiz = [0] * COLUMNS * ROWS


def main(img_file_names, invert_image=False):
    print("Configuration: ")
    print(f"  ROM Clock Frequency: {ROM_CLOCK_FREQ/1000000} MHz")
    print(f"  Video Horizontal Frequency: {DCONFIGS[DISPLAY_TYPE]['HORIZONTAL_FREQ']/1000} KHz")
    print(f"  Video Vertical Frequency: {DCONFIGS[DISPLAY_TYPE]['VERTICAL_FREQ']} Hz")
    print(f"  Calculated Number of lines per frame: {ROWS}")
    print(f"  Calculated Pixel duration: {HOR_RES} uS")
    print(f"  Calculated Number of pixels per line: {COLUMNS}")
    images=[]
    for input_image_name in img_file_names:
        print("Processing input image: %s" % input_image_name)
        image = Image.open(input_image_name).convert('RGB').resize((int(DCONFIGS[DISPLAY_TYPE]["VID_DURATION"]/HOR_RES),DCONFIGS[DISPLAY_TYPE]["VID_LINES"]))
        if invert_image:
            image=ImageOps.invert(image)
        image = image.load()
        images.append(image)
    basefilename = os.path.splitext(img_file_names[0])[0]
    
    # Vertical drive
    for i in range(DCONFIGS[DISPLAY_TYPE]["VERT_DRIVE_LINES"]):
        for j in range(COLUMNS):
            grid_array_vert[i * COLUMNS + j] = 1

    # Vert drive offset
    for i in range(int(abs(DCONFIGS[DISPLAY_TYPE]["VERT_DRIVE_START_OFFSET"])/HOR_RES)):
        grid_array_vert[COLUMNS * ROWS - (i+1)] = 1

    # Horizontal drive
    for i in range(ROWS):
        for j in range(int(DCONFIGS[DISPLAY_TYPE]["HOR_DRIVE_DURATION"]/HOR_RES)):
            grid_array_horiz[i*COLUMNS+j] = 1

    # Video
    grid_arrays_vid = []
    for image in images:
        grid_array_vid = [0] * COLUMNS* ROWS
        for x in range(int(DCONFIGS[DISPLAY_TYPE]["VID_DURATION"]/HOR_RES)): # Video duration
            for y in range(DCONFIGS[DISPLAY_TYPE]["VID_LINES"]):
                p = image[x,y]
                pixel_average = (p[0] + p[1] + p[2]) / 3
                if pixel_average > 127:
                    pixel_value = 1
                else:
                    pixel_value = 0
                grid_array_vid[(y+DCONFIGS[DISPLAY_TYPE]["VID_START_LINE"])*COLUMNS+(x+int(DCONFIGS[DISPLAY_TYPE]["VID_START_OFFSET"]/HOR_RES))] = pixel_value
        grid_arrays_vid.append(grid_array_vid)

    # Create an image as output
    for i, input_image_name in enumerate(img_file_names):
        test_image = Image.new('RGB', (COLUMNS, ROWS)) # Create a new black image
        for x in range(COLUMNS):
            for y in range(ROWS):
                test_image.putpixel((x, y), (grid_array_horiz[y*COLUMNS+x]*255, grid_arrays_vid[i][y*COLUMNS+x]*255, grid_array_vert[y*COLUMNS+x]*255))
        img_out_filename = NAME+'_'+os.path.splitext(input_image_name)[0]+'.png'
        print("Writing output image: %s" % img_out_filename)
        test_image.resize((1024,1024),Image.Resampling.NEAREST).save(img_out_filename, "PNG")

    output = []
    for i in range(ROWS*COLUMNS):
        v = 0b00000000
        # Video starts at bit 0 for first image
        for bit, grid_array_vid in enumerate(grid_arrays_vid):
            v = v | (( 1 - int(grid_array_vid[i]))   << bit)  # Video
        v = v | ((     int(grid_array_horiz[i])) << 5)  # Horiz
        
        v = v | (( 1 - int(grid_array_vert[i]))  << 6)  # Vert
        output.append(v)

    # Add reset on last byte
    v = output[ROWS*COLUMNS-1]
    v = v | (1 << 7)
    output[ROWS*COLUMNS-1]=v

    rom_out_filename = NAME+'_'+basefilename+'.bin'
    print("Writing output ROM: %s" % rom_out_filename)
    f = open(rom_out_filename, 'wb')
    f.write(bytes(output))
    f.close()


if __name__ == "__main__":
    print("== Begin %s" % NAME)
    parser = argparse.ArgumentParser(description='%s Convert image to ROM for test image.' % NAME)
    parser.add_argument('--invert', action=argparse.BooleanOptionalAction, help='Invert image colours')
    parser.add_argument('img_file_names', type=str, nargs='+', help='Path and name of image files.')
    args = parser.parse_args()   
    main(args.img_file_names, args.invert)
    print("== End %s" % NAME)