import os
from contextlib import nullcontext

from PIL import Image

from supysonic.db import AlbumArtist, TrackArtist, db
from supysonic.tool import read_dict_from_json, write_dict_to_json


IMAGE_SIZES = {
  "small": (240, 240),
  "medium": (600, 600),
  "large": (1200, 1200),
}


def resolvePrimaryArtist(artist):
  visitedArtistIds = set()
  currentArtist = artist

  while getattr(currentArtist, "real_artist", None):
    artistId = getattr(currentArtist, "id", id(currentArtist))
    if artistId in visitedArtistIds:
      raise ValueError("Primary artist mapping contains a cycle")
    visitedArtistIds.add(artistId)
    currentArtist = currentArtist.real_artist

  return currentArtist


def getArtistMetadataDirectory(config, artist):
  baseDir = config["BASE"].get("tempdatafolder") or config["WEBAPP"]["cache_dir"]
  return os.path.join(baseDir, "artist", str(artist.id))


def getArtistMetadataPath(config, artist):
  if getattr(artist, "artist_info_json", None):
    return artist.artist_info_json
  return os.path.join(getArtistMetadataDirectory(config, artist), "info.json")


def loadArtistMetadata(config, artist):
  infoPath = getArtistMetadataPath(config, artist)
  payload = read_dict_from_json(infoPath)
  if "image" not in payload or not isinstance(payload["image"], dict):
    payload["image"] = {}
  if "biography" not in payload:
    payload["biography"] = ""
  return infoPath, payload


def saveArtistImages(config, artist, imageFile):
  imageDir = getArtistMetadataDirectory(config, artist)
  os.makedirs(imageDir, exist_ok=True)

  try:
    if hasattr(imageFile, "seek"):
      imageFile.seek(0)
    sourceImage = Image.open(imageFile)
    sourceImage.load()
  except Exception as exc:
    raise ValueError("Invalid artist image") from exc

  sourceImage = sourceImage.convert("RGB")
  imagePaths = {}
  for sizeName, maxSize in IMAGE_SIZES.items():
    resizedImage = sourceImage.copy()
    resizedImage.thumbnail(maxSize)
    imagePath = os.path.join(imageDir, f"{sizeName}.png")
    resizedImage.save(imagePath, format="PNG")
    imagePaths[sizeName] = imagePath
  return imagePaths


def updateArtistMetadata(config, artist, biography=None, imageFile=None):
  infoPath, payload = loadArtistMetadata(config, artist)
  if biography is not None:
    payload["biography"] = biography
  if imageFile is not None:
    payload["image"] = saveArtistImages(config, artist, imageFile)

  write_dict_to_json(payload, infoPath)
  if getattr(artist, "artist_info_json", None) != infoPath:
    artist.artist_info_json = infoPath
    artist.save()
  return infoPath


def assignPrimaryArtist(oldArtist, primaryArtist):
  resolvedPrimaryArtist = resolvePrimaryArtist(primaryArtist)
  oldArtistId = getattr(oldArtist, "id", id(oldArtist))
  resolvedPrimaryArtistId = getattr(resolvedPrimaryArtist, "id", id(resolvedPrimaryArtist))

  if oldArtistId == resolvedPrimaryArtistId:
    raise ValueError("Primary artist must be different from the current artist")

  transactionContext = db.atomic() if getattr(db, "obj", None) is not None else nullcontext()

  with transactionContext:
    for album in list(oldArtist.albums):
      album.artist = resolvedPrimaryArtist
      album.save()

    for track in list(oldArtist.tracks):
      track.artist = resolvedPrimaryArtist
      track.save()

    for relation in list(oldArtist.artist_albums):
      if not hasattr(relation, "album_id"):
        relation.artist_id = resolvedPrimaryArtist
        relation.save()
        continue
      existingRelation = AlbumArtist.get_or_none(
        AlbumArtist.album_id == relation.album_id,
        AlbumArtist.artist_id == resolvedPrimaryArtist,
      )
      if existingRelation is not None:
        existingRelation.position = min(existingRelation.position, relation.position)
        existingRelation.save()
        relation.delete_instance()
      else:
        relation.artist_id = resolvedPrimaryArtist
        relation.save()

    for relation in list(oldArtist.artist_tracks):
      if not hasattr(relation, "track_id"):
        relation.artist_id = resolvedPrimaryArtist
        relation.save()
        continue
      existingRelation = TrackArtist.get_or_none(
        TrackArtist.track_id == relation.track_id,
        TrackArtist.artist_id == resolvedPrimaryArtist,
      )
      if existingRelation is not None:
        existingRelation.position = min(existingRelation.position, relation.position)
        existingRelation.save()
        relation.delete_instance()
      else:
        relation.artist_id = resolvedPrimaryArtist
        relation.save()

    oldArtist.real_artist = resolvedPrimaryArtist
    oldArtist.save()
  return resolvedPrimaryArtist
