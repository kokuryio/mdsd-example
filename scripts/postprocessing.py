import sys
import re
import os

# This script takes the following inputs: Input PlantUML file location, output PlantUML file location, base package,
# source root folder, list of packages to exclude, list of classes to exclude

# It takes the input PlantUMl file and generates an output PlantUMl file, in which the given packages and classes are excluded.
# It also matches method colors of any API operations in any Controller class of the source folder to the colors used in Swagger documentation
# Lastly, it removes the given base package from the name of any class/method/parameter in the output PlantUML file.


# Customizable colors for the API methods in RestControllers
HTTP_COLORS = {
    "GET":    "#6CC644",
    "POST":   "#49CC90",
    "PUT":    "#FCA130",
    "DELETE": "#F93E3E",
}

# Removes the given base package from a given line of PlantUML
def strip_package_line(line, base_package):
    pattern = re.escape(base_package) + r'(?=\w)'
    return re.sub(pattern, '', line)

# Checks whether the given class name is in the classes to be excluded
def is_excluded_class(class_name, exclude_classes):
    return class_name in exclude_classes

# Checks whether the given package name is in the packages to be excluded
def is_excluded_package(full_class_or_pkgname, exclude_packages):
    return any(full_class_or_pkgname.startswith(pkg) for pkg in exclude_packages)

# Loads the input PlantUML file and removes any class included in the given packages/classes to exclude from it
def load_and_filter_plantuml(input_file, base_package, exclude_packages, exclude_classes):
    filtered_lines = []
    class_re = re.compile(r'^\s*class\s+([\w\.]+)')
    with open(input_file, 'r', encoding='utf-8') as fin:
        skip_mode = False
        open_braces = 0
        for line in fin:
            m_class = class_re.match(line)
            if not skip_mode and m_class:
                full_class = m_class.group(1)
                simple_class = full_class.split('.')[-1]
                full_cmp = re.sub('^' + re.escape(base_package), '', full_class)
                if is_excluded_class(simple_class, exclude_classes) or is_excluded_package(full_cmp, exclude_packages):
                    skip_mode = True
                    open_braces = line.count('{') - line.count('}')
                    if open_braces <= 0 and '{' not in line:
                        skip_mode = False
                    continue
                else:
                    filtered_lines.append(line)
                    open_braces = line.count('{') - line.count('}')
                continue
            if skip_mode:
                open_braces += line.count('{')
                open_braces -= line.count('}')
                if open_braces <= 0:
                    skip_mode = False
                continue
            else:
                filtered_lines.append(line)
    return filtered_lines

# Colorizes the API methods based on the method matching given to this method in the output PlantUMl file
def colorize_plantuml_lines(plantuml_lines, output_file, base_package, controllers_map):
    current_class = None
    class_for_lookup = None
    class_re = re.compile(r'^\s*class\s+([\w\.]+)')
    method_re = re.compile(r'^\s*\{method\}[^\w]*[\+\-\#\s]*([\w]+)\s*\(')
    with open(output_file, 'w', encoding='utf-8') as fout:
        for line in plantuml_lines:
            new_line = strip_package_line(line, base_package)
            m_class = class_re.match(new_line)
            if m_class:
                current_class = m_class.group(1)
                simple_class = current_class.split('.')[-1]
                if not simple_class.endswith("Controller"):
                    fout.write(new_line)
                    class_for_lookup = None
                    continue
                class_for_lookup = simple_class
                fout.write(new_line)
                continue
            m_method = method_re.match(new_line)
            if class_for_lookup and m_method:
                method_name = m_method.group(1)
                http_map = controllers_map.get(class_for_lookup, {})
                verb = http_map.get(method_name)
                if verb and verb in HTTP_COLORS:
                    new_line = f"<color: {HTTP_COLORS[verb]}>{new_line.rstrip()} </color>\n"
                fout.write(new_line)
            else:
                fout.write(new_line)

# Finds all Java files that end with "Controller" in the root directory
def find_java_files(root_dir):
    java_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith("Controller.java"):
                java_files.append(os.path.join(dirpath, f))
    return java_files

# Checks whether the given Java files are controllers and extracts a mapping of their API methods to the
# the corresponding API methods
def extract_controllers(java_file):
    with open(java_file, encoding='utf-8', errors='ignore') as f:
        lines = list(f)

    is_controller = False
    controller_name = None
    results = []
    current_verb = None

    controller_anno = re.compile(r'@(RestController|Controller)\b')
    class_decl = re.compile(r'class\s+(\w+)')
    mapping_anno = re.compile(r'@(GetMapping|PostMapping|PutMapping|DeleteMapping)|@RequestMapping\b')
    request_method = re.compile(r'method\s*=\s*RequestMethod\.(GET|POST|PUT|DELETE)')
    method_decl = re.compile(r'(public|private|protected)\s+[\w<>\[\],\s]+\s+(\w+)\s*\(')

    for idx, line in enumerate(lines):
        if controller_anno.search(line):
            is_controller = True
        if is_controller and class_decl.search(line):
            controller_name = class_decl.search(line).group(1)
            break

    if not is_controller or not controller_name:
        return []

    i = 0
    num_lines = len(lines)
    while i < num_lines:
        line_strip = lines[i].strip()
        if mapping_anno.search(line_strip):
            annotation = line_strip
            open_parens = annotation.count('(') - annotation.count(')')
            j = i + 1
            while open_parens > 0 and j < num_lines:
                next_line = lines[j].strip()
                annotation += ' ' + next_line
                open_parens += next_line.count('(') - next_line.count(')')
                j += 1

            m = re.search(r'@(GetMapping|PostMapping|PutMapping|DeleteMapping)', annotation)
            rm = request_method.search(annotation)
            found_http_method = False
            current_verb = None
            if m:
                current_verb = m.group(1).replace("Mapping", "").upper()
                found_http_method = True
            elif rm:
                current_verb = rm.group(1)
                found_http_method = True
            if found_http_method:
                look_k = j
                lines_to_check = []
                non_anno_lines_collected = 0
                max_lines = 3
                while look_k < num_lines and non_anno_lines_collected < max_lines:
                    current = lines[look_k].strip()
                    if current.startswith("@") or not current:
                        look_k += 1
                        continue
                    lines_to_check.append(current)
                    look_k += 1
                    non_anno_lines_collected += 1
                found_method = False
                method_name = None
                for n in range(1, len(lines_to_check) + 1):
                    combined = " ".join(lines_to_check[:n])
                    m2 = method_decl.search(combined)
                    if m2:
                        method_name = m2.group(2)
                        found_method = True
                        break
                if found_method and method_name and current_verb:
                    results.append((method_name, current_verb))
                current_verb = None
                i = look_k
            else:
                i += 1
        else:
            i += 1

    return [(controller_name, results)] if results else []

# Finds controllers in given source folder and maps methods in it to API operations
def build_controller_method_http_map(project_root):
    controllers_map = {}
    for java_file in find_java_files(project_root):
        for controller, method_map in extract_controllers(java_file):
            controllers_map[controller] = dict(method_map)
    return controllers_map

def main(plantuml_in, plantuml_out, base_package, src_root,
         exclude_packages, exclude_classes):
    if not base_package.endswith('.'):
        print("Please provide a valid base package. Needs to end with .")
        sys.exit(1)
    print("\n==== Filtering PlantUML input ====")
    uml_lines = load_and_filter_plantuml(plantuml_in, base_package, exclude_packages, exclude_classes)
    print(f"Filtered {plantuml_in} lines: {len(uml_lines)} retained")
    print(f"\n==== Scanning {src_root} for controllers and method mappings ====")
    controllers_map = build_controller_method_http_map(src_root)
    print("\n==== Controller Map Summary ====")
    for k, v in controllers_map.items():
        print(f"{k}: {v}")
    print("\n==== Starting PlantUML coloring ====")
    colorize_plantuml_lines(uml_lines, plantuml_out, base_package, controllers_map)
    print(f"\n==== DONE ====\nColorized PlantUML written to {plantuml_out}")

if __name__ == '__main__':
    if len(sys.argv) != 7:
        print("Usage: python plantuml_controller_colorizer.py "
              "plantuml_in.txt plantuml_out.txt base.package. path/to/src "
              "excluded_packages_csv excluded_classes_csv")
        print("Example: python plantuml_controller_colorizer.py "
              "uml_in.txt uml_out.txt com.example. src/main/java "
              "com.foo.bar.,com.example.skip. IgnoredController,SomeOtherClass")
        sys.exit(1)
    exclude_packages = [p for p in sys.argv[5].split(',') if p]
    exclude_classes = [c for c in sys.argv[6].split(',') if c]
    main(
        sys.argv[1],        # plantuml_in.txt
        sys.argv[2],        # plantuml_out.txt
        sys.argv[3],        # base.package.
        sys.argv[4],        # src_root
        exclude_packages,
        exclude_classes
    )
