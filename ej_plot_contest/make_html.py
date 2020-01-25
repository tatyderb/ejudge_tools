import pathlib
import sys

from jinja2 import Environment, FileSystemLoader

def main():
    template = sys.argv[1]
    output = sys.argv[2]

    base_dir = pathlib.Path.cwd()
    template_path = base_dir / template
    template_dir = template_path.parent
    template_file = template_path.name
    
    
    print(f'path: {template}')
    print(f'dir:  {template_dir}')
    print(f'dir:  {template_dir.resolve()}')
    print(f'file: {template_file}')
    if template_path.exists():
        print(f'File exist {template_path}')
    else:
        print(f'NO FILE {template_path}')
        

    env = Environment(loader=FileSystemLoader([template_dir.resolve()]))
    template = env.get_template(template_file)

    output_from_parsed_template = template.render()
    # output_from_parsed_template = template.render(header=header[2:], body=body, footer=footer)
    print(output_from_parsed_template)
    
    with open(output, 'w', encoding='utf8') as fout:
        print(output_from_parsed_template, file=fout)


if __name__ == '__main__':
    main()
    