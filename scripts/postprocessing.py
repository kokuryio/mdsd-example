import sys
import re

# Swagger/OpenAPI style colors
HTTP_COLORS = {
    "GET":    "#6cc644",
    "POST":   "#49cc90",
    "PUT":    "#fca130",
    "DELETE": "#f93e3e",
}

HTTP_LABELS = {
    "GET":    "GET",
    "POST":   "POST",
    "PUT":    "PUT",
    "DELETE": "DELETE",
}

def strip_package_line(line, base_package):
    pattern = re.escape(base_package) + r'(?=\w)'
    return re.sub(pattern, '', line)

def main(input_file, output_file, base_package):
    if not base_package.endswith('.'):
        print("Please provide a valid base package. Needs to end with .")
        sys.exit(1)

    with open(input_file, 'r') as fin, open(output_file, 'w') as fout:
        for line in fin:
            # Remove base package from each line
            new_line = strip_package_line(line, base_package)
            fout.write(new_line)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python strip_plantuml_package.py input.puml output.puml com.example.project")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
