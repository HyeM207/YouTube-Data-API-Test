from OpenSSL import SSL
import flask
from flask import redirect, url_for, render_template
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
import google.auth.transport.requests
import google.oauth2.credentials
import google_auth_oauthlib.flow

from config import  CLIENT_ID ,SECRET_KEY

CLIENT_SECRETS_FILE = "client_secret.json"

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

app = flask.Flask(__name__)
app.secret_key = SECRET_KEY

@app.route('/')
def index():
  # print("확인 : ", CLIENT_ID ,SECRET_KEY)
  if 'credentials' not in flask.session:
    return flask.redirect('authorize')

  return flask.redirect(flask.url_for('subscriptions'))


@app.route('/authorize')
def authorize():
  # print("[authorize] 시작")
  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES)
  flow.redirect_uri = flask.url_for('oauth2callback', _external=True)
  authorization_url, state = flow.authorization_url(
      access_type='offline',
      prompt='consent',
      include_granted_scopes='true')

  flask.session['state'] = state

  return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    # print("[oauth2callback] 시작")
    state = flask.session['state']
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    # 세션에 credentials 정보 저장
    credentials = flow.credentials
    flask.session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    return flask.redirect(flask.url_for('subscriptions'))

'''
    내가 구독한 계정 리스트 반환 -> 각 채널별 최근 video_id 추출 ->  video_id로 상세 영상 정보 획득 
    # 참고 :  api docs : https://developers.google.com/youtube/v3/docs/subscriptions/list?hl=ko
'''
@app.route('/subscriptions')
def subscriptions():
    # print("[subscriptions] 시작")
    if 'credentials' not in flask.session:
        return redirect(url_for('index'))
    credentials = Credentials.from_authorized_user_info(flask.session['credentials'], SCOPES)
    youtube = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
    subscriptions = []
   
    request = youtube.subscriptions().list(
        part='snippet',
        mine=True,
        order='alphabetical',
        maxResults=50
    )

    print("[subscriptions] session 확인 ", flask.session['credentials'])
    while request:
        response = request.execute()
        for item in response['items']:
            subscriptions.append(item['snippet']['title'])

            # ======  구독한 channel Id로 가장 최근 video id 가져오기  ======  
            channel_id = [item['snippet']['resourceId']['channelId'] ]
        
            videos_response = youtube.search().list(
                part='id',
                channelId=','.join(channel_id),
                type='video',
                order='date',
                maxResults=1
            ).execute()

            # video 응답 중 가장 최근의 videoID 추출 
            video_id = videos_response['items'][0]['id']['videoId'] 
            print("\n\n채널명 : ", item['snippet']['title'], " video_id : " , video_id)

            # ======  Video ID로 music track 불러오기  ======  
            musics_response = youtube.videos().list(
                    part='contentDetails',
                    id=video_id
                ).execute()

            # response에서 음악 트랙 추출 
            content_details = musics_response['items'][0]['contentDetails']
            if 'music' in content_details:
                music_tracks = content_details['music']['songs']
                print("music_tracks : " , music_tracks)

        request = youtube.subscriptions().list_next(request, response)
   
    return render_template('subscriptions.html', subscriptions=subscriptions)


if __name__ == '__main__':
# 계속 실행하다보니 session 쌓일거 같아서 실행할때마다 삭제해줌
  flask.session.clear() 

  # OAuth 2.0인증하려면 Https 접속 필수 => SSL 인증서 받아서 적용해줌
  context = SSL.Context(SSL.PROTOCOL_TLS)
  context.load_cert_chain('cert.pem', 'key.pem')

  app.run('localhost', 5000, ssl_context=context, debug=True)