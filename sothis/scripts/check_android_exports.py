#!/usr/bin/env python3
"""Run the production export file boundary on the JVM; no Android device required."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
TEST = r'''package za.co.zalens;
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;
public final class ExportTest {
 interface Checked {void run()throws Exception;}
 static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
 static void denied(Checked work)throws Exception{try{work.run();throw new AssertionError("Expected export rejection");}catch(IOException expected){}}
 public static void main(String[] args)throws Exception{
  File root=new File(args[0]),cache=new File(root,"cache");cache.mkdirs();
  byte[] content="A credited public record\n".getBytes("UTF-8");
  File staged=LocalExports.stage(cache,"exports","research.txt",content);
  check(LocalExports.restore(cache,staged.getPath()).equals(staged.getCanonicalFile()),"Restore only actual private staging");
  ByteArrayOutputStream out=new ByteArrayOutputStream();check(LocalExports.copy(staged,out)==content.length,"Byte count");
  check(Arrays.equals(content,out.toByteArray()),"Exact saved content");
  check(LocalExports.displayName("../name\n.txt").indexOf('/')<0,"Display name excludes path syntax");
  denied(()->LocalExports.restore(cache,new File(root,"outside.txt").getPath()));
  denied(()->LocalExports.restore(cache,new File(cache,"exports/../outside.txt").getPath()));
  denied(()->LocalExports.restore(cache,new File(cache,"exports/not-a-private-export.txt").getPath()));
  denied(()->LocalExports.restore(cache,new File(cache,"exports/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.txt").getPath()));
  denied(()->LocalExports.stage(cache,"exports","huge.bin",new byte[LocalExports.MAX_BYTES+1]));
  denied(()->LocalExports.newFile(cache,"../../escape","x.txt"));
  File shared=LocalExports.stage(cache,"share","bundle.zip",content);check(shared.getName().endsWith(".bin"),"Provider-compatible sharing name");
  denied(()->LocalExports.restore(cache,shared.getPath()));
  File outside=new File(root,"outside");outside.mkdirs();File linkedCache=new File(root,"linked-cache");linkedCache.mkdirs();
  Files.createSymbolicLink(new File(linkedCache,"exports").toPath(),outside.toPath());
  File outsideMatch=new File(outside,"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.txt");Files.write(outsideMatch.toPath(),content);
  denied(()->LocalExports.restore(linkedCache,outsideMatch.getPath()));
  denied(()->LocalExports.newFile(linkedCache,"exports","x.txt"));
  denied(()->LocalExports.copy(staged,null));
  denied(()->LocalExports.write(staged,()->new OutputStream(){public void write(int b)throws IOException{throw new IOException("Destination full");}}));
  check(Arrays.equals(Files.readAllBytes(staged.toPath()),content),"Failed destination preserves prepared source");
  Thread.currentThread().interrupt();try{denied(()->LocalExports.write(staged,()->new ByteArrayOutputStream()));}finally{Thread.interrupted();}

  // Simulate an Activity recreation during a save: cancel the first writer while
  // its replacement waits. The replacement must open/truncate after the old one closes.
  byte[] large=new byte[65536];new Random(7).nextBytes(large);File prepared=LocalExports.stage(cache,"exports","recreated.bin",large);
  File destination=new File(root,"saved.bin");CountDownLatch firstWrite=new CountDownLatch(1);boolean[] interrupted={false};Throwable[] failure={null};
  Thread old=new Thread(()->{try{LocalExports.write(prepared,()->new FilterOutputStream(new FileOutputStream(destination)){
   boolean first=true;public void write(byte[] b,int offset,int length)throws IOException{
    out.write(b,offset,length);if(first){first=false;firstWrite.countDown();try{Thread.sleep(5000);}catch(InterruptedException expected){Thread.currentThread().interrupt();}}
   }});}catch(IOException expected){interrupted[0]=true;}});
  Thread replacement=new Thread(()->{try{LocalExports.write(prepared,()->new FileOutputStream(destination));}catch(Throwable error){failure[0]=error;}});
  old.start();check(firstWrite.await(5,TimeUnit.SECONDS),"Old save began");replacement.start();old.interrupt();old.join(5000);replacement.join(5000);
  check(!old.isAlive()&&!replacement.isAlive()&&interrupted[0]&&failure[0]==null,"Interrupted writer and replacement finish");
  check(Arrays.equals(Files.readAllBytes(destination.toPath()),large),"Recreated writer produces exact complete file");
  File completed=LocalExports.stage(cache,"exports","completed.txt",content);String completedPath=completed.getPath();
  check(!LocalExports.isFinished(cache,completedPath),"Unfinished saves have no completion token");
  LocalExports.markFinished(cache,completed);completed.delete();
  check(LocalExports.isFinished(cache,completedPath),"Stale completed Bundle is recognized after source removal");
  denied(()->LocalExports.restore(cache,completedPath));
  File cancelled=LocalExports.stage(cache,"exports","cancelled.txt",content);String cancelledPath=cancelled.getPath();
  LocalExports.markFinished(cache,cancelled);cancelled.delete();
  check(LocalExports.isFinished(cache,cancelledPath),"Stale cancelled Bundle is recognized after source removal");
  File failed=LocalExports.stage(cache,"exports","failed.txt",content);String failedPath=failed.getPath();failed.delete();
  check(!LocalExports.isFinished(cache,failedPath),"Missing failed save is not mistaken for completion");
  denied(()->LocalExports.restore(cache,failedPath));
  for(int i=0;i<40;i++){File done=LocalExports.stage(cache,"exports","done.txt",content);LocalExports.markFinished(cache,done);done.delete();}
  File[] markers=new File(cache,"exports").listFiles((dir,name)->name.endsWith(".done"));
  check(markers.length<=32,"Completion checkpoints stay bounded");
  for(File marker:markers)check(marker.length()==0,"Checkpoint retains no user data");
  // Cleanup keeps the active save, caps recent abandoned saves, expires old shares,
  // and leaves unrelated cache entries alone.
  File unrelated=new File(cache,"exports/unrelated.txt");Files.write(unrelated.toPath(),content);
  for(int i=0;i<14;i++)LocalExports.stage(cache,"exports","abandoned.txt",content);
  shared.setLastModified(System.currentTimeMillis()-25*3600000L);LocalExports.cleanup(cache,staged);
  File[] survivors=new File(cache,"exports").listFiles((dir,name)->name.matches("[a-f0-9]{32}\\.(png|jpg|pdf|txt|html|eml|docx|zip|bin)"));
  check(staged.isFile()&&survivors.length<=9&&unrelated.isFile()&&!shared.exists(),"Cleanup bounds and retained save");
  System.out.println("Native export boundary passed: exact bytes, safe restoration, traversal/symlink rejection, size/provider bounds, write failures, interrupted recreation, completion/cancellation tokens and bounded cleanup.");
 }
}'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ecj', required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        source = folder / 'za/co/zalens/ExportTest.java'
        source.parent.mkdir(parents=True)
        source.write_text(TEST)
        classes = folder / 'classes'
        classes.mkdir()
        production = ROOT / 'android/app/src/main/java/za/co/zalens/LocalExports.java'
        subprocess.run(['java', '-jar', str(args.ecj), '-8', '-d', str(classes), str(production), str(source)], check=True)
        subprocess.run(['java', '-cp', str(classes), 'za.co.zalens.ExportTest', str(folder)], check=True)


if __name__ == '__main__':
    main()
