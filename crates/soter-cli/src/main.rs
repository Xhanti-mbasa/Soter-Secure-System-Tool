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
        --passwd PASSWORD    Set a soterspace password
    -U, --unlock             Remove a soterspace password
    -s, --network SSID PASS  Configure Wi-Fi for a soterspace
        --openvpn FILE       Attach an OpenVPN profile
        --unsafe             Relax strict network fail-closed behavior
        --backup             Back up a soterspace
        --bzip               Compress a backup
        --bunzip             Decompress a backup
        --restore FILE       Restore a soterspace backup
    -h, --human-readable     Display output in a human-readable format
    -E, --extended-regexp    Interpret patterns as extended regular expressions
        --help               Display this help and exit
"#;

#[derive(Debug, Default)]
struct Cli {
    create: bool,
    empty: bool,
    remove: bool,
    modify: bool,
    list: bool,
    all: bool,
    temporary: bool,
    unlock: bool,
    human_readable: bool,
    extended_regexp: bool,
    passwd: Option<String>,
    network_ssid: Option<String>,
    network_password: Option<String>,
    openvpn: Option<String>,
    unsafe_network: bool,
    backup: bool,
    bzip: bool,
    bunzip: bool,
    restore: Option<String>,
    arguments: Vec<String>,
}

impl Cli {
    fn parse() -> Result<Self, String> {
        let mut cli = Self::default();
        let mut args = env::args().skip(1);

        while let Some(arg) = args.next() {
            match arg.as_str() {
                "-c" | "--create" => cli.create = true,
                "-e" | "--empty" => cli.empty = true,
                "-ce" | "-ec" => {
                    cli.create = true;
                    cli.empty = true;
                }
                "-r" | "--remove" => cli.remove = true,
                "-m" | "--modify" => cli.modify = true,
                "-l" | "--list" => cli.list = true,
                "-a" | "--all" => cli.all = true,
                "-T" | "--temporary" => cli.temporary = true,
                "-U" | "--unlock" => cli.unlock = true,
                "--passwd" => {
                    cli.passwd = Some(args.next().ok_or("--passwd requires a password")?);
                }
                "-s" | "--network" => {
                    cli.network_ssid = Some(args.next().ok_or("--network requires an SSID")?);
                    cli.network_password = Some(args.next().unwrap_or_default());
                }
                "--openvpn" => {
                    cli.openvpn = Some(args.next().ok_or("--openvpn requires a file")?);
                }
                "--unsafe" => cli.unsafe_network = true,
                "--backup" => cli.backup = true,
                "--bzip" => cli.bzip = true,
                "--bunzip" => cli.bunzip = true,
                "--restore" => {
                    cli.restore = Some(args.next().ok_or("--restore requires a backup file")?);
                }
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
        println!("Soter — secure Linux workspace manager");
        return;
    }

    println!("{cli:?}");
}
