use std::{env, process};

const USAGE: &str = r#"Soter — secure Linux system configuration

Usage:
    soter [options] [arguments]...

Options:
    -c, --create             Create a namespace
    -r, --remove             Remove a namespace
    -m, --modify             Modify a namespace
    -l, --list               List namespaces
    -a, --all                Include all namespaces
    -h, --human-readable     Display output in a human-readable format
    -E, --extended-regexp    Interpret patterns as extended regular expressions
        --help               Display this help and exit
"#;

#[derive(Debug, Default)]
struct Cli {
    create: bool,
    remove: bool,
    modify: bool,
    list: bool,
    all: bool,
    human_readable: bool,
    extended_regexp: bool,
    arguments: Vec<String>,
}

impl Cli {
    fn parse() -> Result<Self, String> {
        let mut cli = Self::default();

        for arg in env::args().skip(1) {
            match arg.as_str() {
                "-c" | "--create" => cli.create = true,
                "-r" | "--remove" => cli.remove = true,
                "-m" | "--modify" => cli.modify = true,
                "-l" | "--list" => cli.list = true,
                "-a" | "--all" => cli.all = true,
                "-h" | "--human-readable" => cli.human_readable = true,
                "-E" | "--extended-regexp" => cli.extended_regexp = true,
                "--help" => {
                    print!("{USAGE}");
                    process::exit(0);
                }
                _ if arg.starts_with('-') => return Err(format!("unknown option: {arg}")),
                _ => cli.arguments.push(arg),
            }
        }

        Ok(cli)
    }
}

fn main() {
    let cli = Cli::parse().unwrap_or_else(|error| {
        eprintln!("soter: {error}");
        eprintln!("Try 'soter --help' for more information.");
        process::exit(2);
    });

    if env::args().len() == 1 {
        println!("Soter — secure Linux system configuration");
        return;
    }

    // Namespace operations are parsed here. Their system-level implementation
    // will be connected to soter-core and soter-system as those operations land.
    println!("{cli:?}");
}
