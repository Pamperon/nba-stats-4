import os
from unittest.mock import patch, Mock

def test_boxscore_includes_original_espn_player_id():
    with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN':'test','ODDSPAPI_API_KEY':'test'}):
        import main
    response=Mock()
    response.json.return_value={'header':{'competitions':[{'status':{'type':{'state':'post'}}}]},'boxscore':{'players':[{'team':{'displayName':'Boston Celtics'},'statistics':[{'labels':['MIN','PTS','REB','AST'],'athletes':[{'athlete':{'id':'22','displayName':'Alex Test'},'stats':['30','25','5','4']}]}]}]}}
    with patch.object(main.requests,'get',return_value=response):
        result=main.public_nba_boxscore('123456')
    assert result['teams'][0]['players'][0]['id']=='22'
    assert result['teams'][0]['players'][0]['points']=='25'
    assert result['odds_api_calls']==0
