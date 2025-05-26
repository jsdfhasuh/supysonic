import musicbrainzngs
musicbrainzngs.set_useragent(app="test",version="0.1")
result = musicbrainzngs.get_artist_by_id(id = '15518da5-4b36-4f17-bfb4-7c3e6973bc90')
pass