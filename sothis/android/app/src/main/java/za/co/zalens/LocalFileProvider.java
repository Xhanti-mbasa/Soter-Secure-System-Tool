package za.co.zalens;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.webkit.MimeTypeMap;
import java.io.File;
import java.io.FileNotFoundException;

/** Private, narrowly scoped content URIs with per-intent temporary permissions. */
public final class LocalFileProvider extends ContentProvider {
    @Override public boolean onCreate(){return true;}
    private File file(Uri uri)throws FileNotFoundException{
        String area=uri.getPathSegments().size()==2?uri.getPathSegments().get(0):"",name=uri.getLastPathSegment();
        if(area.equals("share")&&name.matches("[a-f0-9]{32}\\.(png|jpg|pdf|txt|eml|docx|bin)"))return new File(new File(getContext().getCacheDir(),"share"),name);
        if(area.equals("evidence")&&name.matches("[a-f0-9]{64}\\.(pdf|html|bin|txt)"))return new File(new File(getContext().getFilesDir(),"evidence"),name.substring(0,64));
        if(area.equals("capture")&&name.matches("[a-f0-9]{32}\\.jpg"))return new File(new File(getContext().getCacheDir(),"capture"),name);
        throw new FileNotFoundException("Unknown private file");
    }
    @Override public String getType(Uri uri){String ext=MimeTypeMap.getFileExtensionFromUrl(uri.toString());String type=MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);return type==null?"application/octet-stream":type;}
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
        File f=file(uri);if(!"r".equals(mode)){if(!uri.getPathSegments().get(0).equals("capture")||!(mode.equals("w")||mode.equals("wt")||mode.equals("rw")||mode.equals("rwt")))throw new FileNotFoundException("Read-only export");f.getParentFile().mkdirs();return ParcelFileDescriptor.open(f,ParcelFileDescriptor.parseMode(mode));}return ParcelFileDescriptor.open(f,ParcelFileDescriptor.MODE_READ_ONLY);
    }
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){try{File f=file(uri);String[] columns=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor c=new MatrixCursor(columns);Object[] values=new Object[columns.length];for(int i=0;i<columns.length;i++)values[i]=columns[i].equals(OpenableColumns.DISPLAY_NAME)?f.getName():columns[i].equals(OpenableColumns.SIZE)?f.length():null;c.addRow(values);return c;}catch(Exception e){return null;}}
    @Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
    @Override public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
    @Override public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
}
