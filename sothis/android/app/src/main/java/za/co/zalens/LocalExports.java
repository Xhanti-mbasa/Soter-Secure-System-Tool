package za.co.zalens;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.io.FilenameFilter;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;
import java.util.Arrays;
import java.util.Comparator;

/** App-private export staging, shared by current and restored save operations. */
final class LocalExports {
    static final int MAX_BYTES=20*1024*1024;
    private static final String EXTENSIONS="png|jpg|pdf|txt|html|eml|docx|zip|bin";

    static String displayName(String name) {
        String clean=(name==null?"":name).replaceAll("[^a-zA-Z0-9._-]","_");
        return clean.isEmpty()?"sothis-export":clean.substring(0,Math.min(clean.length(),160));
    }
    static File newFile(File cache,String area,String name)throws IOException {
        if(!"exports".equals(area)&&!"share".equals(area))throw new IOException("Invalid export area");
        File root=new File(cache.getCanonicalFile(),area);
        if(!root.getCanonicalFile().equals(root.getAbsoluteFile()))throw new IOException("Invalid export folder");
        if(!root.isDirectory()&&!root.mkdirs())throw new IOException("Export storage is unavailable");
        String lower=displayName(name).toLowerCase(Locale.US);
        String ext=lower.matches(".*\\.("+EXTENSIONS+")$")?lower.substring(lower.lastIndexOf('.')+1):"bin";
        // LocalFileProvider's existing sharing contract exposes only these extensions.
        if("share".equals(area)&&!ext.matches("png|jpg|pdf|txt|eml|docx|bin"))ext="bin";
        return new File(root,UUID.randomUUID().toString().replace("-","")+"."+ext);
    }
    static File stage(File cache,String area,String name,byte[] data)throws IOException {
        if(data.length>MAX_BYTES)throw new IOException("File limit is 20 MiB");
        File file=newFile(cache,area,name);
        try(FileOutputStream out=new FileOutputStream(file)){out.write(data);}
        catch(IOException error){file.delete();throw error;}
        return file;
    }
    static File stageText(File cache,String name,String text)throws IOException {
        if(text==null)throw new IOException("Export content is missing");
        if(text.length()>MAX_BYTES)throw new IOException("File limit is 20 MiB");
        return stage(cache,"exports",name,text.getBytes(StandardCharsets.UTF_8));
    }
    private static File exportPath(File cache,String path)throws IOException {
        if(path==null||path.isEmpty())throw new IOException("Export file is missing");
        File root=new File(cache.getCanonicalFile(),"exports");
        if(!root.getCanonicalFile().equals(root.getAbsoluteFile()))throw new IOException("Invalid export folder");
        File file=new File(path).getCanonicalFile();
        if(!root.equals(file.getParentFile())||!file.getName().matches("[a-f0-9]{32}\\.("+EXTENSIONS+")"))
            throw new IOException("Pending export is unavailable; prepare it again");
        return file;
    }
    static File restore(File cache,String path)throws IOException {
        File file=exportPath(cache,path);
        if(!file.isFile())throw new IOException("Pending export is unavailable; prepare it again");
        return file;
    }
    static boolean isFinished(File cache,String path)throws IOException {
        File file=exportPath(cache,path);
        return new File(file.getParentFile(),file.getName()+".done").isFile();
    }
    static synchronized void markFinished(File cache,File file)throws IOException {
        File validated=exportPath(cache,file.getPath());
        // Empty random-token checkpoints survive a stale saved Bundle without retaining user data.
        try(FileOutputStream out=new FileOutputStream(new File(validated.getParentFile(),validated.getName()+".done"))){out.getFD().sync();}
        trimCheckpoints(validated.getParentFile());
    }
    private static void trimCheckpoints(File root){
        File[] markers=root.listFiles(new FilenameFilter(){public boolean accept(File dir,String name){return name.matches("[a-f0-9]{32}\\.("+EXTENSIONS+")\\.done");}});
        if(markers==null)return;
        Arrays.sort(markers,new Comparator<File>(){public int compare(File a,File b){return Long.compare(b.lastModified(),a.lastModified());}});
        for(int i=32;i<markers.length;i++)markers[i].delete();
    }
    static synchronized void cleanup(File cache,File retained)throws IOException {
        File keep=retained==null?null:retained.getCanonicalFile();
        for(String area:new String[]{"exports","share"}){
            File root=new File(cache.getCanonicalFile(),area);
            if(!root.getCanonicalFile().equals(root.getAbsoluteFile()))continue;
            File[] files=root.listFiles();if(files==null)continue;
            Arrays.sort(files,new Comparator<File>(){public int compare(File a,File b){return Long.compare(b.lastModified(),a.lastModified());}});
            int recentOrphans=0;
            for(File file:files){
                if(!file.getName().matches("[a-f0-9]{32}\\.("+EXTENSIONS+")")||file.getCanonicalFile().equals(keep))continue;
                boolean old=System.currentTimeMillis()-file.lastModified()>24*3600000L;
                boolean finished="exports".equals(area)&&new File(root,file.getName()+".done").isFile();
                // Keep at most eight recent unfinished saves. Shared files need their 24-hour handoff window.
                if(finished||old||("exports".equals(area)&&++recentOrphans>8))file.delete();
            }
            if("exports".equals(area))trimCheckpoints(root);
        }
    }
    interface Destination {OutputStream open()throws IOException;}
    static synchronized long write(File file,Destination destination)throws IOException {
        // Open/truncate only after a cancelled Activity's worker has released the lock.
        if(Thread.currentThread().isInterrupted())throw new IOException("Export interrupted");
        try(OutputStream out=destination.open()){return copy(file,out);}
    }
    static long copy(File file,OutputStream out)throws IOException {
        if(out==null)throw new IOException("The selected destination cannot be written");
        long total=0;
        try(FileInputStream in=new FileInputStream(file)){
            byte[] bytes=new byte[8192];int count;
            while((count=in.read(bytes))!=-1){
                if(Thread.currentThread().isInterrupted())throw new IOException("Export interrupted");
                out.write(bytes,0,count);total+=count;
            }
        }
        out.flush();return total;
    }
}
