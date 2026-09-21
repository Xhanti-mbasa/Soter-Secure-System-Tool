use std::{env, process};

const USAGE: &str = r#"Soter — secure Linux workspace manager

Usage:
    soter [options] [soterspace] [command]...

Workspace options:
    -c, --create             Create a soterspace
    -e, --empty              Create the soterspace empty (combine as -ce)
    -r, --remove             Remove a soterspace
    -m, --modify             Modify a soterspace
    -l, --list               List soterspaces
    -a, --all                Include all soterspaces
    -T, --temporary          Mark the soterspace as temporary
    -h, --human-readable     Display output in a human-readable format
    -E, --extended-regexp    Interpret patterns as extended regular expressions
        --help               Display this help and exit
"#;

#[derive(Debug, Default)]
struct Cli {
    create: bool, empty: bool, remove: bool, modify: bool, list: bool,
    all: bool, temporary: bool, human_readable: bool, extended_regexp: bool,
    arguments: Vec<String>,
}

impl Cli {
    fn parse() -> Result<Self, String> {
        let mut cli = Self::default();
        for arg in env::args().skip(1) {
            match arg.as_str() {
                "-c" | "--create" => cli.create = true,
                "-e" | "--empty" => cli.empty = true,
                "-ce" | "-ec" => { cli.create = true; cli.empty = true; }
                "-r" | "--remove" => cli.remove = true,
                "-m" | "--modify" => cli.modify = true,
                "-l" | "--list" => cli.list = true,
                "-a" | "--all" => cli.all = true,
                "-T" | "--temporary" => cli.temporary = true,
                "-h" | "--human-readable" => cli.human_readable = true,
                "-E" | "--extended-regexp" => cli.extended_regexp = true,
                "--help" => { print!("{USAGE}"); process::exit(0); }
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
    if env::args().len() == 1 { println!("Soter — secure Linux workspace manager"); return; }
    println!("{cli:?}");
}
