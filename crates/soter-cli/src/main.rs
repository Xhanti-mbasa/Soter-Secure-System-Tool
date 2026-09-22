use std::{env, path::Path, process};
use soter_system::soterspace;

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
        --shell SHELL        Select the shell used inside a soterspace
        --flakes PACKAGE...  Select Nix flake applications (firefox, chromium, ...)
        --network MODE       Network mode: open or isolate
        --network -l wifi    List host Wi-Fi networks
        --openvpn FILE       Attach an OpenVPN profile
        --unsafe             Relax strict network fail-closed behavior
        --backup             Back up a soterspace
        --bzip               Compress a backup
        --bunzip             Decompress a backup
        --restore FILE       Restore a soterspace backup
    -h, --human-readable     Display output in a human-readable format
    -E, --extended-regexp    Interpret patterns as extended regular expressions
        --help               Display this help and exit
        --version            Display the Soter version and exit

Commands:
    help                     Display this help and exit

Examples:
    soter -c lab             Create and enter 'lab'
    soter lab               Enter 'lab'
    soter -l                List soterspaces
    soter --shell zsh lab    Enter 'lab' using zsh
    soter --flakes firefox chromium lab
    soter --network isolate lab
    soter --network -l wifi
    soter lab -- ip addr     Run a command inside 'lab'
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
    shell: Option<String>,
    flakes: Vec<String>,
    network_mode: Option<String>,
    network_list: Option<String>,
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
        let mut args = env::args().skip(1).peekable();

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
                "--shell" => {
                    cli.shell = Some(args.next().ok_or("--shell requires a shell")?);
                }
                "--flakes" => {
                    while let Some(value) = args.peek() {
                        if value.starts_with('-') || value == "help" {
                            break;
                        }
                        cli.flakes.push(args.next().unwrap());
                    }
                    if cli.flakes.is_empty() {
                        return Err("--flakes requires at least one package".into());
                    }
                }
                "--network" => {
                    let value = args.next().ok_or("--network requires 'open', 'isolate', or '-l wifi'")?;
                    if value == "-l" || value == "--list" {
                        cli.network_list = Some(args.next().ok_or("--network --list requires a category (for example: wifi)")?);
                    } else if matches!(value.as_str(), "open" | "isolate") {
                        cli.network_mode = Some(value);
                    } else {
                        return Err(format!("unknown network option: {value}; expected open, isolate, or -l wifi"));
                    }
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
                "--version" => {
                    println!("soter {}", env!("CARGO_PKG_VERSION"));
                    process::exit(0);
                }
                "--" => {
                    cli.arguments.extend(args);
                    break;
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
        println!("Try 'soter --help' to get started.");
        return;
    }

    if cli.arguments.first().map(String::as_str) == Some("help") {
        print!("{USAGE}");
        return;
    }

    let target = cli.arguments.first().cloned();

    let result: Result<(), String> = if let Some(category) = &cli.network_list {
        if category == "wifi" {
            soterspace::list_wifi()
        } else {
            Err(format!("unknown network list category: {category}"))
        }
    } else if let Some(file) = &cli.restore {
        soterspace::restore(Path::new(file)).map(|_| println!("Restored '{file}'."))
    } else if cli.list {
        soterspace::list().map(|spaces| {
            if spaces.is_empty() { println!("No soterspaces."); }
            else { for space in spaces { println!("{space}"); } }
        })
    } else if cli.create {
        match target.as_deref() {
            Some(name) => soterspace::create(name, cli.empty, cli.temporary).and_then(|space| {
                println!("Created soterspace '{}' at {}.", space.name, space.path.display());
                println!("Entering soterspace '{}'...", space.name);
                soterspace::enter_or_run(&space.name, &[], cli.shell.as_deref(), &cli.flakes, cli.network_mode.as_deref()).and_then(|code| {
                    if code == 0 { Ok(()) } else { Err(format!("soterspace exited with status {code}")) }
                })
            }),
            None => Err("create requires a soterspace name".into()),
        }
    } else if cli.remove {
        match target.as_deref() {
            Some(name) => soterspace::remove(name).map(|_| println!("Removed soterspace '{name}'.")),
            None => Err("remove requires a soterspace name".into()),
        }
    } else if cli.backup {
        match target.as_deref() {
            Some(name) => {
                let filename = format!("{name}.soter");
                soterspace::backup(name, Path::new(&filename))
                    .map(|_| println!("Backed up '{name}' to '{filename}'."))
            }
            None => Err("backup requires a soterspace name".into()),
        }
    } else if let Some(name) = target.as_deref() {
        if let Some(password) = &cli.passwd {
            soterspace::set_value(name, "password", password).map(|_| println!("Password set for '{name}'."))
        } else if cli.unlock {
            soterspace::remove_value(name, "password").map(|_| println!("Password removed from '{name}'."))
        } else if let Some(profile) = &cli.openvpn {
            let value = format!("profile={profile}\nfail_closed={}\n", !cli.unsafe_network);
            soterspace::set_value(name, "openvpn.conf", &value).map(|_| println!("OpenVPN configuration saved for '{name}'."))
        } else if cli.modify {
            Err("modify requires a setting such as --passwd, --network, or --openvpn".into())
        } else {
            let command = cli.arguments.iter().skip(1).cloned().collect::<Vec<_>>();
            soterspace::enter_or_run(name, &command, cli.shell.as_deref(), &cli.flakes, cli.network_mode.as_deref()).and_then(|code| {
                if code == 0 { Ok(()) } else { Err(format!("command exited with status {code}")) }
            })
        }
    } else {
        Err("no soterspace or operation specified".into())
    };

    if let Err(error) = result {
        eprintln!("soter: {error}");
        process::exit(1);
    }
}
