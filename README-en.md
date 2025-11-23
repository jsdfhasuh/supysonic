# Supysonic

Supysonic is a Python implementation of the [Subsonic][] server API.

![Build Status](https://github.com/spl0k/supysonic/workflows/Tests/badge.svg)
[![codecov](https://codecov.io/gh/spl0k/supysonic/branch/master/graph/badge.svg)](https://codecov.io/gh/spl0k/supysonic)
![Python](https://img.shields.io/badge/python-3.7+-blue.svg)

Current supported features are:
* browsing (by folders or tags)
* streaming of various audio file formats
* transcoding
* user or random playlists
* cover art
* starred tracks/albums and ratings
* [Last.fm][lastfm] scrobbling
* [ListenBrainz][listenbrainz] scrobbling
* Jukebox mode
* Get artists cover art and album cover art from Spotify (NEW)
* Get Artists information from localnfo (NEW)
* add some New API (NEW)

Supysonic currently targets the version 1.12.0 of the Subsonic API. For more
details, go check the [API implementation status][docs-api].

[subsonic]: http://www.subsonic.org/
[lastfm]: https://www.last.fm/
[listenbrainz]: https://listenbrainz.org/
[docs-api]: https://supysonic.readthedocs.io/en/latest/api.html

## Documentation

Full documentation is available at https://supysonic.readthedocs.io/

## Quickstart

Use the following commands to install Supysonic, create an admin user, define a
library folder, scan it and start serving on port 5722 using [Gunicorn][].

    $ pip install supysonic
    $ pip install gunicorn
    $ supysonic-cli user add MyUserName
    $ supysonic-cli user setroles --admin MyUserName
    $ supysonic-cli folder add MyLibrary /home/username/Music
    $ supysonic-cli folder scan MyLibrary
    $ supysonic-server

You should now be able to enjoy your music with the client of your choice!

But using only the above commands will use a default configuration and
especially storing the database in a temporary directory. Head over to the
documentaiton for [full setup instructions][docs-setup], plus other options if
you don't want to use Gunicorn.

Note that there's also an optional [daemon][docs-daemon] that watches for
library changes and provides support for other features such as the
jukebox mode.

[gunicorn]: https://gunicorn.org/
[docs-setup]: https://supysonic.readthedocs.io/en/latest/setup/index.html
[docs-daemon]: https://supysonic.readthedocs.io/en/latest/setup/daemon.html

## Development stuff

For those wishing to collaborate on the project, since Supysonic uses [Flask][]
you can use its development server which provides automatic reloading and
in-browser debugging among other things. To start said server:

    $ export FLASK_APP="supysonic.web:create_application()"
    $ export FLASK_ENV=development
    $ flask run

And there's also the tests (which require `lxml` to run):

    $ pip install lxml
    $ python -m unittest
    $ python -m unittest tests.net.suite

The last command runs a few tests that make HTTP requests to remote third-party
services (namely Last.fm, ListenBrainz and ChartLyrics).

[flask]: https://flask.palletsprojects.com/

##nfo rule
If you want to use the localinfo feature,you need to follow the rules.
1. The nfo file must be named as album.nfo in the track folder
2. The nfo file must be in xml format
3. The nfo file must contain the following tags:
   - `<album>`: The root element for the album information.
   - `<track>`: Each track should be enclosed in this tag.
   - `<lock_data>`: A boolean value indicating whether the data is locked (optional).
   the following tags must be included in each `<track>` element:
    - `<title>`: The title of the track.
    - `<cdnum>`: The CD number (if applicable),must be a integer.
    - `<position>`: The position of the track on the CD.
4. The following tags are optional but recommended:
   - `<artist>`: The artist of the track.
   - `<albumartist>`: The album artist (optional).
   - `<year>`: The year of the album (optional).
sample_album.nfo:
```xml
<?xml version="1.0" encoding="utf-8"?>
<album>
  <lock_data>False</lock_data>
  <track>
    <title>Many Shades Of Black</title>
    <cdnum>1</cdnum>
    <position>10</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Best For Last</title>
    <cdnum>1</cdnum>
    <position>02</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Chasing Pavements</title>
    <cdnum>1</cdnum>
    <position>03</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Cold Shoulder</title>
    <cdnum>1</cdnum>
    <position>04</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Crazy For You</title>
    <cdnum>1</cdnum>
    <position>05</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Melt My Heart To Stone</title>
    <cdnum>1</cdnum>
    <position>06</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>First Love</title>
    <cdnum>1</cdnum>
    <position>07</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Right As Rain</title>
    <cdnum>1</cdnum>
    <position>08</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Make You Feel My Love</title>
    <cdnum>1</cdnum>
    <position>09</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>My Same</title>
    <cdnum>1</cdnum>
    <position>10</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Tired</title>
    <cdnum>1</cdnum>
    <position>11</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Hometown Glory</title>
    <cdnum>1</cdnum>
    <position>12</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Chasing Pavements</title>
    <cdnum>1</cdnum>
    <position>01</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Melt My Heart To Stone</title>
    <cdnum>1</cdnum>
    <position>02</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>That's It, I Quit, I'm Moving On</title>
    <cdnum>1</cdnum>
    <position>03</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Crazy For You</title>
    <cdnum>1</cdnum>
    <position>04</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Right As Rain</title>
    <cdnum>1</cdnum>
    <position>05</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>My Same</title>
    <cdnum>1</cdnum>
    <position>06</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Make You Feel My Love</title>
    <cdnum>1</cdnum>
    <position>07</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Daydreamer</title>
    <cdnum>1</cdnum>
    <position>08</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Hometown Glory</title>
    <cdnum>1</cdnum>
    <position>09</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Daydreamer</title>
    <cdnum>1</cdnum>
    <position>01</position>
    <artist>Adele</artist>
  </track>
  <artist>Adele</artist>
  <albumartist>Adele</albumartist>
</album>
```
