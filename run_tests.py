import subprocess, sys, shlex

SCRIPT = 'v0.4/bootstrap/use_tokenize.py'

def run():
    cmd = f"python3 {SCRIPT}"
    print('Running:', cmd)
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, _ = p.communicate()
    print(out)
    if p.returncode != 0:
        print('Bootstrap run failed (non-zero exit)')
        sys.exit(2)
    # basic checks
    if 'Interpreting program built from H# parser' in out and '\n1\n' in out:
        print('Bootstrap pipeline OK')
        sys.exit(0)
    else:
        print('Bootstrap output did not match expectations')
        sys.exit(3)

if __name__ == '__main__':
    run()
