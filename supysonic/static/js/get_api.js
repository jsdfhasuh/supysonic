
async function getAlbum(album_url = null,pageSize = 20,offset = 0,password = '') {
    const albumurl = album_url;
    const response = await fetch(albumurl + `?f=json&type=newest&size=${pageSize}&offset=${offset}` + password);
    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    
    const data = await response.json();
    const rawalbum = data["subsonic-response"].albumList2.album;
    
    return rawalbum;
}

async function getArtists(artists_url = null,password = '') {
    const artistApiUrl = artists_url;
    const response  = await fetch(artistApiUrl + '?f=json&' + password);
    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    
    const data = await response.json();
    const artists = {};
    
    for (const group of data['subsonic-response'].artists.index) {
        for (const artist of group.artist) {
            artists[artist.id] = artist.name;
        }
    }
    
    return artists;
}
// /rest/getAlbum?id=8d13c233-2704-44db-bf3a-bd41eff90417&u=root&v=1.15.0&c=Musiver&s=PfaDfv&t=7f844528050875231e1039658d711800
async function getAlbumByid (album_id = null,password = '',album_url = null) 
{
    const albumApiUrl = album_url;
    const response  = await fetch(albumApiUrl + `?f=json&id=${album_id}` + password);
    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    
    const data = await response.json();
    const album = data['subsonic-response'].album;
    
    return album;
}
    