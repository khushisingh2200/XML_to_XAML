import os
import glob
import xml.etree.ElementTree as ET
import configparser
import logging

# Dictionaries to store extracted data
parent_dict = {}
shape_dict = {}
crule_dict = {}

def load_config(config_path):
    """
    Loads the configuration file.

    Args:
        config_path (str): Path to the config.ini file.

    Returns:
        configparser.ConfigParser object if the file is found, else None.
    """
    config = configparser.ConfigParser()
    # Check if config file exists
    if os.path.isfile(config_path):
        config.read(config_path)
        return config
    else:
        print("Config file not found.")
        return None


def validate_config(config):
    """
    Validates the config file settings.

    Args:
        config (configparser.ConfigParser): preloaded object.

    Returns:
        bool: True if valid, False otherwise.
    """
    try:
        # Fetch paths and format from config
        input_folder = config['SETTINGS']['input_folder']
        output_folder = config['SETTINGS']['output_folder']
        file_format = config['SETTINGS']['file_format']

        # Check if input folder exists
        if not os.path.isdir(input_folder):
            print("Input folder not found: {}".format(input_folder))
            return False

        # Create output folder if it doesn't exist
        if not os.path.isdir(output_folder):
            print("Output folder not found. Creating it at {}".format(output_folder))
            os.makedirs(output_folder)

        # Validate file format
        if file_format not in ["xml", "ini"]:
            print("Invalid file format specified.")
            return False

        return True

    except KeyError as e:
        print("Missing key in config: {}".format(e))
        return False


def get_files(input_folder, file_format):
    """
    Gets all files with the specified format in the input folder.

    Args:
        input_folder (str): Path to the input folder.
        file_format (str): Desired file format like 'xml'

    Returns:
        list: List of file paths.
    """
    # Create file search pattern
    file_pattern = os.path.join(input_folder, f"*.{file_format}")
    return glob.glob(file_pattern)


def decimal_to_hex(color_val):
    """
    Converts a decimal color value to a hex string.

    Args:
        color_val (str): Color value in decimal.

    Returns:
        str: Hexadecimal color value.
    """
    # Default gray color if color_val is None or invalid
    if not color_val:
        return "#808080"
    try:
        return "#{:06X}".format(int(color_val))
    except ValueError:
        return "#808080"


def has_crule(shape_obj):
    """
    Checks if a shape object has a RULE element.

    Args:
        shape_obj (xml.Element): Shape object element.

    Returns:
        bool: True if RULE element is found, False otherwise.
    """
    return shape_obj.find('RULE') is not None


def extract_children_text(elem):
    """
    Extracts text from child elements.

    Args:
        elem (xml.Element): Parent XML element.

    Returns:
        dict: Dictionary with tag names and their text content.
    """
    data = {}
    # Loop through child elements
    for child in elem:
        # Check if child has sub-elements
        if list(child):
            for subchild in child:
                if subchild.text and subchild.text.strip():
                    # Create a nested key with parent.child structure
                    data["{}.{}".format(child.tag, subchild.tag)] = subchild.text.strip()
        elif child.text and child.text.strip():
            data[child.tag] = child.text.strip()
    return data


def extract_rule_details(rule_elem):
    """
    Extracts details from a RULE element.

    Args:
        rule_elem (xml.Element): RULE element.

    Returns:
        dict: Key-value pairs of rule data.
    """
    return {child.tag: child.text.strip() for child in rule_elem if child.text and child.text.strip()}


def extract_visuals(shape):
    """
    Extracts visual properties like stroke, fill, and thickness from a shape.

    Args:
        shape (xml.Element): SHAPE element.

    Returns:
        tuple: Stroke color, stroke thickness, and fill color.
    """
    stroke = fill = stroke_thickness = None

    # Extract Pen details
    pen = shape.find('Pen')
    if pen is not None:
        stroke = decimal_to_hex(pen.findtext('Color'))

    # Extract FillColor details
    fill_color = shape.find('FillColor')
    if fill_color is not None:
        fill = decimal_to_hex(fill_color.findtext('Color'))

    # Extract Style details
    style = shape.find('Style')
    if style is not None:
        stroke_thickness = style.findtext('StrokeThickness')

    # Extract ShapeStyle details
    shape_style = shape.find('ShapeStyle')
    if shape_style is not None:
        if not stroke:
            stroke = decimal_to_hex(shape_style.findtext('LineColor'))
        if not fill:
            fill = decimal_to_hex(shape_style.findtext('FillColor'))

    # Default values if not set
    return stroke or "#808080", stroke_thickness or "1", fill or "#808080"


# ---------- Parse Function ----------
def parse_xml(xml_file):
    """
    Parses an XML file and extracts shape data to generate XAML elements.

    Args:
        xml_file (str): Path to the XML file.

    Returns:
        tuple: A list of XAML canvas elements, canvas width, and canvas height.
    """
    global parent_dict, shape_dict, crule_dict

    # Parse the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()
    counter=0

    # Initialize canvas elements and boundary coordinates
    canvas_elements = []
    min_x = None
    max_x = None
    min_y = None
    max_y = None

    # Iterate through each ViewObject in the XML
    for viewobject in root.findall('.//ViewObject'):
        # Clear dictionaries for each ViewObject
        parent_dict.clear()
        shape_dict.clear()
        crule_dict.clear()

        # Extract and update parent_dict with data from the ViewObject
        parent_dict.update(extract_children_text(viewobject))
        symbol_key = parent_dict.get('SymbolKey', '0')
        sysname = parent_dict.get('SysName', 'default')

        # Locate SHAPEARRAY containing shape objects
        shape_array = viewobject.find('SHAPEARRAY')
        if shape_array is None:
            continue  # Skip if no SHAPEARRAY found

        # Iterate through each ShapeObject in the SHAPEARRAY
        for idx, shapeobject in enumerate(shape_array.findall('.//ShapeObject')):
            # Locate SHAPE element
            shape = shapeobject.find('.//SHAPE')
            if shape is None:
                continue

            # Extract the class name (CRectangle, CTextBox, etc.)
            classname = shape.find('./MetaData/ClassName').text

            # Check if the shape has a RULE element
            rule_present = has_crule(shapeobject)
            # Determine visibility based on the presence of RULE
            visibility = "Collapsed" if rule_present else "Visible"

            # Construct a unique shape key
            shape_key = 'shape_{}'.format(idx)

            # Extract visual properties (stroke, thickness, fill)
            stroke, stroke_thickness, fill = extract_visuals(shape)

            # Extract rule data if a RULE element is present
            if rule_present:
                crule_elem = shapeobject.find('RULE')
                crule_dict.update(extract_rule_details(crule_elem))

            # Handle CRectangle shapes
            if classname == 'CRectangle':
                # Extract RectShape data
                counter+=1
                rect = shape.find('RectShape')
                left = int(rect.findtext('Left'))
                right = int(rect.findtext('Right'))
                top = int(rect.findtext('Top'))
                bottom = int(rect.findtext('Bottom'))


                # Calculate width and height
                width = right - left
                height = bottom - top

                # Update min and max coordinates for canvas size calculation
                min_x = left if min_x is None else min(min_x, left)
                max_x = right if max_x is None else max(max_x, right)
                min_y = top if min_y is None else min(min_y, top)
                max_y = bottom if max_y is None else max(max_y, bottom)

                # Update shape_dict with rectangle data
                shape_dict[shape_key] = {
                    'ClassName': "{}-rect-{}".format(sysname, symbol_key),
                    'Visibility': visibility,
                    'Tag': '1',
                    'Left': left,
                    'Top': top,
                    'Width': width,
                    'Height': height,
                    'Stroke': stroke,
                    'StrokeThickness': stroke_thickness,
                    'Fill': fill

                }

                # Append rectangle XAML element
                canvas_elements.append(
                    '<Rectangle Name="{sysname}-rect-{symbol_key}-{counter}" Width="{width}" Height="{height}" '
                    'Canvas.Left="{left}" Canvas.Top="{top}" Stroke="{stroke}" StrokeThickness="{stroke_thickness}" '
                    'Fill="{fill}" Tag="1" Visibility="{visibility}" Canvas.ZIndex="2"/>'.format(
                        sysname=sysname,
                        symbol_key=symbol_key,
                        counter=counter,
                        width=width,
                        height=height,
                        left=left,
                        top=top,
                        stroke=stroke,
                        stroke_thickness=stroke_thickness,
                        fill=fill,
                        visibility=visibility
                    )
                )

            # Handle CTextBox shapes
            elif classname == 'CTextBox':
                # Extract RectShape data for the text box
                counter+=1
                rect = shape.find('Rectangle/RectShape')
                left = int(rect.findtext('Left'))
                right = int(rect.findtext('Right'))
                top = int(rect.findtext('Top'))
                bottom = int(rect.findtext('Bottom'))

                # Update min and max coordinates for canvas size calculation
                min_x = left if min_x is None else min(min_x, left)
                max_x = right if max_x is None else max(max_x, right)
                min_y = top if min_y is None else min(min_y, top)
                max_y = bottom if max_y is None else max(max_y, bottom)

                # Update shape_dict with text box data
                shape_dict[shape_key] = {
                    'ClassName': "{}-txt-{}".format(sysname, symbol_key),
                    'Visibility': visibility,
                    'Tag': '1',
                    'Left': left,
                    'Top': top,
                    'Right': right,
                    'Bottom': bottom,
                    'Text': 'control'
                }

                # Append text box XAML element
                canvas_elements.append(
                    '<TextBlock Name="{sysname}-txt-{symbol_key}-{counter}" Text="control" '
                    'Canvas.Left="{left}" Canvas.Top="{top}" Canvas.Right="{right}" Canvas.Bottom="{bottom}" '
                    'Foreground="#808080" FontSize="10" FontWeight="Normal" Tag="1" Visibility="{visibility}"/>'.format(
                        sysname=sysname,
                        symbol_key=symbol_key,
                        counter=counter,
                        left=left,
                        top=top,
                        right=right,
                        bottom=bottom,
                        visibility=visibility
                    )
                )

            # Handle CPolygon and CParallelogram shapes
            elif classname in ['CPolygon', 'CParallelogram']:
                counter+=1
                points = []

                # Extract all points for the polygon or parallelogram
                for pt in shape.findall('PolyShape/Point'):
                    x = int(pt.findtext('X'))
                    y = int(pt.findtext('Y'))
                    points.append(f"{x},{y}")

                    # Update min and max coordinates for canvas size calculation
                    min_x = x if min_x is None else min(min_x, x)
                    max_x = x if max_x is None else max(max_x, x)
                    min_y = y if min_y is None else min(min_y, y)
                    max_y = y if max_y is None else max(max_y, y)

                # Update shape_dict with polygon data
                shape_dict[shape_key] = {
                    'ClassName': "{}-poly-{}".format(sysname, symbol_key),
                    'Visibility': visibility,
                    'Tag': '17',
                    'Points': " ".join(points),
                    'Stroke': stroke,
                    'StrokeThickness': stroke_thickness,
                    'Fill': fill
                }

                # Append polygon XAML element
                canvas_elements.append(
                    '<Polygon Name="{sysname}-poly-{symbol_key}-{counter}" Points="{points}" '
                    'Stroke="{stroke}" StrokeThickness="{stroke_thickness}" Fill="{fill}" '
                    'Tag="17" Visibility="{visibility}" Canvas.ZIndex="2"/>'.format(
                        sysname=sysname,
                        symbol_key=symbol_key,
                        counter=counter,
                        points=" ".join(points),
                        stroke=stroke,
                        stroke_thickness=stroke_thickness,
                        fill=fill,
                        visibility=visibility
                    )
                )

        # Determine canvas size based on min and max coordinates
        if min_x is not None and max_x is not None and min_y is not None and max_y is not None:
            canvas_width = max_x - min_x
            canvas_height = max_y - min_y
        else:
            # Default canvas size if no shapes found
            canvas_width = 800
            canvas_height = 600

    # Return the generated XAML elements and canvas size
    return canvas_elements

def validate_conversion_all(input_folder, output_folder, file_format="xml"):
    # Ensure we’re building a valid glob pattern like *.xml
    pattern = "*.{}".format(file_format.lstrip('*.'))
    search_path = os.path.join(input_folder, pattern)
    print("DEBUG: Searching for XML files to validate in: {}".format(search_path))
    xml_files = glob.glob(search_path)
    print("DEBUG: Found XML files: {}".format(xml_files))

    if not xml_files:
        print("No XML files found matching '{}' in {} for validation.".format(pattern, input_folder))
        return

    for xml_file in xml_files:
        base_name = os.path.basename(xml_file)
        xaml_file = os.path.join(output_folder, base_name.replace(".xml", ".xaml"))

        if not os.path.exists(xaml_file):
            print(" Warning: Output file for {} not found: {}".format(base_name, xaml_file))
            continue
        validate_conversion(xml_file, xaml_file)

def validate_conversion(xml_file, xaml_file):
    """Validate if all elements and attributes in XML are present in XAML."""
    try:
        print("\n🔍 Validating: {} ↔ {}".format(xml_file, xaml_file))

        # Parse XML and XAML files
        tree = ET.parse(xml_file)
        root = tree.getroot()

        xaml_tree = ET.parse(xaml_file)
        xaml_root = xaml_tree.getroot()

        # Gather all tags and attribute values from XAML
        xaml_tags = set()
        xaml_attributes = set()
        for x_elem in xaml_root.iter():
            xaml_tags.add(x_elem.tag)
            for attr_val in x_elem.attrib.values():
                xaml_attributes.add(str(attr_val))

        mismatches = []

        # Loop through XML elements
        for i, elem in enumerate(root.iter()):
            if elem.tag.lower() == 'root':
                continue

            if i % 100 == 0 and i > 0:
                print("  ...Checked {} elements".format(i))

            # Check tag existence
            if elem.tag not in xaml_tags:
                mismatches.append("Missing tag: {}".format(elem.tag))

            # Check attribute values
            for attr, value in elem.attrib.items():
                if str(value) not in xaml_attributes:
                    mismatches.append("{} - Missing value: {}={}".format(elem.tag, attr, value))

        # Final result output
        if mismatches:
            logging.warning("Validation failed for %s", xml_file)
            print(" Validation failed for {}. Issues:".format(xml_file))
            for m in mismatches:
                logging.warning(" -> %s", m)
                print("  - {}".format(m))
        else:
            logging.info("Validation successful for %s", xml_file)
            print(" Validation successful for {}".format(xml_file))

    except KeyboardInterrupt:
        print("\n Validation interrupted by user.")
    except Exception as e:
        logging.error("Error during validation for %s: %s", xml_file, str(e))
        print("Error during validation for {}: {}".format(xml_file, str(e)))

def get_input():
    shape_id = input("Enter the full or partial shape ID (e.g., SKN689Tc): ").strip()
    attribute = input("Enter the attribute to check (e.g., Canvas.Left): ").strip()
    xml_path = input("Enter the path to the XML file: ").strip()
    xaml_path = input("Enter the path to the XAML file: ").strip()
    return shape_id, attribute, xml_path, xaml_path

def parse_xml_with_dummy_root(file_path):
    """
    Parse XML or XAML file with multiple root elements.
    Removes BOM and any content before the XML declaration.
    Wraps content in a dummy root element.
    """
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        # Find where the XML declaration starts
        xml_decl_index = content.find('<?xml')
        if xml_decl_index == -1:
            # No XML declaration found; just strip leading whitespace
            content = content.lstrip()
        else:
            # Remove anything before XML declaration
            content = content[xml_decl_index:]

        # Wrap content in dummy root to handle multiple roots
        wrapped_content = "<DummyRoot>\n{}\n</DummyRoot>".format(content)
        root = ET.fromstring(wrapped_content)
        return root
    except Exception as e:
        print("Error reading {}: {}".format(file_path, e))
        return None

def find_matching_shapes(root, shape_id, attribute, is_xml=True):
    """
    Search for all elements whose ID attribute contains shape_id substring.
    Returns list of tuples: (element, shape_id_found, attribute_value)
    """
    if root is None:
        return []

    matches = []
    for elem in root.iter():
        # For XML, check 'id' or 'Name'
        # For XAML, check 'x:Name' or 'Name'
        if is_xml:
            id_attr = elem.attrib.get('id') or elem.attrib.get('Name')
        else:
            id_attr = elem.attrib.get('x:Name') or elem.attrib.get('Name')

        if id_attr:
            if shape_id in id_attr:
                attr_value = elem.attrib.get(attribute)
                matches.append((elem, id_attr, attr_value))

    return matches

def choose_match(matches, attribute, shape_id):
    if not matches:
        return None, None

    if len(matches) == 1:
        elem, found_id, attr_val = matches[0]
        print("One match found: Shape ID = '{}', Attribute '{}' = '{}'".format(found_id, attribute, attr_val))
        return attr_val, found_id

    # Multiple matches found - ask user to select one
    print("Multiple matches found for shape ID containing '{}':".format(shape_id))
    for i, (elem, found_id, attr_val) in enumerate(matches):
        print(" [{}] Shape ID: {}, Attribute '{}': {}".format(i + 1, found_id, attribute, attr_val))

    while True:
        choice = input("Enter the number (1-{}) of the shape to compare: ".format(len(matches))).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                selected = matches[idx]
                return selected[2], selected[1]  # attr_val, found_id
        print("Invalid choice. Try again.")

def compare_attributes(xml_value, xaml_value, attribute, shape_id):
    print("\nComparison Result:")
    if xml_value is None or xaml_value is None:
        print("Comparison failed. One or both values are missing.")
    elif xml_value == xaml_value:
        print("Attribute '{}' matches for shape '{}': {}".format(attribute, shape_id, xml_value))
    else:
        print("Mismatch for attribute '{}' in shape '{}':".format(attribute, shape_id))
        print("  XML : {}".format(xml_value))
        print("  XAML: {}".format(xaml_value))

def compare_shape_attributes():
    shape_id, attribute, xml_path, xaml_path = get_input()

    print("\nParsing XML file...")
    xml_root = parse_xml_with_dummy_root(xml_path)
    xml_matches = find_matching_shapes(xml_root, shape_id, attribute, is_xml=True)
    xml_value, xml_found_id = choose_match(xml_matches, attribute, shape_id)

    if xml_found_id:
        print("Selected XML shape ID: {}".format(xml_found_id))
    else:
        print("No matches found in XML.")

    print("\nParsing XAML file...")
    xaml_root = parse_xml_with_dummy_root(xaml_path)
    xaml_matches = find_matching_shapes(xaml_root, shape_id, attribute, is_xml=False)
    xaml_value, xaml_found_id = choose_match(xaml_matches, attribute, shape_id)

    if xaml_found_id:
        print("Selected XAML shape ID: {}".format(xaml_found_id))
    else:
        print("No matches found in XAML.")

    compare_attributes(xml_value, xaml_value, attribute, shape_id)
