import os
import discord
from discord import Embed
from discord.ext import tasks
from dotenv import load_dotenv
import datetime
import csv
import gc
import dbl

# mariaDB
import mysql.connector
from mysql.connector import Error

load_dotenv()

client = discord.Client()
global people_list
people_list = dict() # 放nickname


# This example uses tasks provided by discord.ext to create a task that posts guild count to top.gg every 30 minutes.
dbl_token = os.getenv('TOPGG_TOKEN')  # set this to your bot's top.gg token
client.dblpy = dbl.DBLClient(client, dbl_token)


@tasks.loop(minutes=30)
async def update_stats():
  # This function runs every 30 minutes to automatically update your server count."""
  try:
    await client.dblpy.post_guild_count()
    print('Posted server count=' + str(client.dblpy.guild_count()))
  except Exception as e:
    print('Failed to post server count\n{}: {}'.format(type(e).__name__, e))

@tasks.loop(hours=12)
async def clear_list():
  # 重設雜湊表
  people_list = dict()
  gc.collect()
  print('已重置雜湊表')

update_stats.start()
clear_list.start()



# 機器人上線事件
@client.event
async def on_ready():
  await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="!h 查看更多資訊!"))
  print('We have logged in as {0.user}'.format(client))

# 全形轉半形
def full2half(s):
  rstring = ""
  for uchar in s:
      u_code = ord(uchar)
      if u_code == 12288:  # 全形空格直接轉換
          u_code = 32
      elif 65281 <= u_code <= 65374:  # 全形字元（除空格）根據關係轉化
          u_code -= 65248
      rstring += chr(u_code)
  return rstring

@client.event
async def on_message(message):
  # 防止機器人自問自答
  if message.author == client.user:
    return

  # 獲取使用者nick(若無則為本名)
  async def get_nick_name(member_id):
    # 新增一個映射表來加速 str(message.guild.id)+str(member_id)
    key = str(message.guild.id) + str(member_id)

    if key in people_list:
      return people_list[key]
    else:
      try:
        user = await client.get_guild(message.guild.id).fetch_member(member_id)
        if user.nick == None:
          people_list[key] = str(user.name)
          return user.name
        else:
          people_list[key] = str(user.nick)
          return user.nick
      except:
        print("get_nick_name查無此人!")
        return "[N/A]"
        

  async def get_mention(member_id):
    try:
      user = await client.get_guild(message.guild.id).fetch_member(member_id)
      return user.mention
    except:
          print("get_mention查無此人!")
          return "[N/A]"
    

  def Check_week(group_progress, week): # (now_week,now_boss,week_offset), week
    if week >= group_progress[0] and week <= group_progress[0] + group_progress[2]: # 檢查週目
      return True
    else:
      return False

  def Check_boss(group_progress, week, boss): # (now_week,now_boss,week_offset), week, boss
    # 檢查Boss
    if boss > 0 and boss < 6 :  
      if week == group_progress[0] and boss < group_progress[1]:
        return False
      else:
        return True
    else:
      return False

  async def Update(server_id, group_serial):
    connection = mysql.connector.connect(host=os.getenv('SQLHOST'), database=os.getenv('SQLDB'), user=os.getenv('SQLID'), password=os.getenv('SQLPW'))
    if connection.is_connected():
      cursor = connection.cursor(prepared=True)
      sql = "SELECT table_style FROM princess_connect.group WHERE server_id = ? and group_serial = ? LIMIT 0, 1"
      data = (server_id, group_serial)
      cursor.execute(sql, data)
      row = cursor.fetchone()
      cursor.close
      if row:
        if row[0] == 0:
          await UpdateEmbed(server_id, group_serial)
        else:
          await UpdateTraditional(server_id, group_serial)
      else:
        await message.channel.send(content='查無戰隊資料!')
      connection.close # 關閉連線
  
  async def UpdateEmbed(server_id, group_serial): # 更新刀表
    try:
      # 查詢當前周目、王、刀表訊息、保留刀訊息
      connection = mysql.connector.connect(host=os.getenv('SQLHOST'), database=os.getenv('SQLDB'), user=os.getenv('SQLID'), password=os.getenv('SQLPW'))
      if connection.is_connected():
        cursor = connection.cursor(prepared=True)
        sql = "SELECT now_week, week_offset, now_boss, table_channel_id, table_message_id, knife_pool_message_id FROM princess_connect.group WHERE server_id = ? and group_serial = ? LIMIT 0, 1"
        data = (server_id, group_serial)
        cursor.execute(sql, data)
        row = cursor.fetchone()
        cursor.close
        if row:
          now_week = row[0]
          week_offset = row[1]
          now_boss = row[2]
          table_channel_id = row[3]
          table_message_id = row[4]
          knife_pool_message_id = row[5]

          if table_message_id:
            embed_msg = Embed(title='第' + str(group_serial) + '戰隊刀表', color=0xD98B99)
            # 刀表部分，從當前週目開始印
            send_msg = ''
            index_boss = now_boss # 僅第一個週目由此王開始
            for i in range(now_week, now_week + week_offset + 1):
              kinfe_msg_name = ''
              for j in range(index_boss,6):              
                if i == now_week and j == now_boss:
                  kinfe_msg_name = kinfe_msg_name + '**'+ str(j) + '王(現在進度)**\n'  # TODO
                else:
                  kinfe_msg_name = kinfe_msg_name + '**'+ str(j) + '王**\n'  # TODO
  
                # 刀表SQL
                cursor = connection.cursor(prepared=True)
                sql = "SELECT member_id, comment FROM princess_connect.knifes WHERE server_id = ? and group_serial = ? and week = ? and boss = ? order by serial_number"
                data = (server_id, group_serial,i ,j)
                cursor.execute(sql, data)
                row = cursor.fetchone()
                index = 1
                while row:
                  nick_name = await get_nick_name(row[0])
                  kinfe_msg_name = kinfe_msg_name + '　{' +str(index) + '} ' + nick_name + '\n　　' +row[1] + '\n'
                  row = cursor.fetchone()
                  index = index +1
                cursor.close()
              index_boss = 1
              embed_msg.add_field(name='\u200b', value='-   -   -   -   -   -   -   -   ', inline=False)
              embed_msg.add_field(name='第' + str(i) + '週目', value=kinfe_msg_name , inline=False)
            
  
          
            try:
              guild = client.get_guild(server_id)
              channel = guild.get_channel(table_channel_id)
              message_obj = await channel.fetch_message(table_message_id)
              await message_obj.edit(embed=embed_msg)
            except:
              await message.channel.send(content='刀表訊息已被移除，請重新設定刀表頻道!')

            # 保留刀部分
            # 從一王印到五王
            # 刀表SQL
            cursor = connection.cursor(prepared=True)
            sql = "SELECT boss, member_id, comment FROM princess_connect.keep_knifes WHERE server_id = ? and group_serial = ? order by boss"
            data = (server_id, group_serial)
            cursor.execute(sql, data)
            msg = ''
            index = 1
            row = cursor.fetchone()
            while row:  
              # {index} ?王 nickname\tcomment\n
              name = await get_nick_name(row[1])
              msg = msg + '{' +str(index) + '} ' + str(row[0]) + '王 ' + name + '\n　' + row[2] + '\n'
              index = index + 1
              row = cursor.fetchone()
            cursor.close
  
            # 修改保留刀表
            if msg == '':
              msg = '尚無保留刀資訊!'
            else:
              pass
            embed_msg = Embed(title='保留刀', color=0xD9ACA3)
            embed_msg.add_field(name='\u200b', value=msg , inline=False)
            

            # 取得訊息物件
            try:
              guild = client.get_guild(server_id)
              channel = guild.get_channel(table_channel_id)
              message_obj = await channel.fetch_message(knife_pool_message_id)
              await message_obj.edit(embed=embed_msg)
            except:
              await message.channel.send(content='保留區訊息已被移除，請重新設定刀表頻道!')

          else:
            await message.channel.send(content='請戰隊隊長設定刀表頻道!')
        else:
          await message.channel.send(content='查無戰隊資料!')
        connection.close # 關閉連線
      else:
        await message.channel.send(content='資料庫連線失敗!')
    except Error as e:
      print("資料庫連接失敗：", e)
    finally:
      if (connection.is_connected()):
          cursor.close()
          connection.close()
          print("資料庫連線已關閉")

  async def UpdateTraditional(server_id, group_serial): # 更新刀表
    try:
      # 查詢當前周目、王、刀表訊息、保留刀訊息
      connection = mysql.connector.connect(host=os.getenv('SQLHOST'), database=os.getenv('SQLDB'), user=os.getenv('SQLID'), password=os.getenv('SQLPW'))
      if connection.is_connected():
        cursor = connection.cursor(prepared=True)
        sql = "SELECT now_week, week_offset, now_boss, table_channel_id, table_message_id, knife_pool_message_id FROM princess_connect.group WHERE server_id = ? and group_serial = ? LIMIT 0, 1"
        data = (server_id, group_serial)
        cursor.execute(sql, data)
        row = cursor.fetchone()
        cursor.close
        if row:
          now_week = row[0]
          week_offset = row[1]
          now_boss = row[2]
          table_channel_id = row[3]
          table_message_id = row[4]
          knife_pool_message_id = row[5]

          if table_message_id:
            # 刀表部分，從當前週目開始印
            send_msg = '```asciidoc\n'
            index_boss = now_boss # 僅第一個週目由此王開始
            for i in range(now_week, now_week + week_offset + 1):
              send_msg = send_msg + '第' + str(i) + '週目:\n'
              for j in range(index_boss,6):
                msg = ''

                # 刀表SQL
                cursor = connection.cursor(prepared=True)
                sql = "SELECT member_id, comment FROM princess_connect.knifes WHERE server_id = ? and group_serial = ? and week = ? and boss = ? order by serial_number"
                data = (server_id, group_serial,i ,j)
                cursor.execute(sql, data)
                row = cursor.fetchone()
                index = 1
                while row:
                  nick_name = await get_nick_name(row[0])
                  msg = msg + '  {' +str(index) + '}' + nick_name + '(' + row[1] + '),\n'
                  row = cursor.fetchone()
                  index = index +1
                cursor.close()
                if i == now_week and j == now_boss:
                  if msg == '':
                    send_msg = send_msg + ' ' + str(j) + '王(當前周目)\n'
                  else:
                    send_msg = send_msg + ' ' + str(j) + '王(當前周目)\n' + msg + '\n'  
                else:
                  if msg == '':
                    send_msg = send_msg + ' ' + str(j) + '王\n'
                  else:
                    send_msg = send_msg + ' ' + str(j) + '王\n' + msg + '\n'  
              index_boss = 1

          
            send_msg = send_msg + '```'
            
            # 取得訊息物件
            try:
              guild = client.get_guild(server_id)
              channel = guild.get_channel(table_channel_id)
              message_obj = await channel.fetch_message(table_message_id)
              await message_obj.edit(content = send_msg)
            except:
              await message.channel.send(content='刀表訊息已被移除，請重新設定刀表頻道!')

            # 保留刀部分
            # 從一王印到五王
            # 刀表SQL
            cursor = connection.cursor(prepared=True)
            sql = "SELECT boss, member_id, comment FROM princess_connect.keep_knifes WHERE server_id = ? and group_serial = ? order by boss"
            data = (server_id, group_serial)
            cursor.execute(sql, data)
            msg = '```asciidoc\n保留刀:\n'
            index = 1
            row = cursor.fetchone()
            while row:  
              # {index} ?王 nickname\tcomment\n
              name = await get_nick_name(row[1])
              msg = msg + '{' +str(index) + '} ' + str(row[0]) + '王 ' + name + '\t' + row[2] + '\n'
              index = index + 1
              row = cursor.fetchone()
            cursor.close

            # 取得訊息物件
            try:
              guild = client.get_guild(server_id)
              channel = guild.get_channel(table_channel_id)
              message_obj = await channel.fetch_message(knife_pool_message_id)
              if msg == '```asciidoc\n保留刀:\n':
                await message_obj.edit(content = '尚無保留刀資訊!')
              else:
                msg = msg + '```'
                await message_obj.edit(content = msg)
            except:
              await message.channel.send(content='保留區訊息已被移除，請重新設定刀表頻道!')

          else:
            await message.channel.send(content='請戰隊隊長設定刀表頻道!')
        else:
          await message.channel.send(content='查無戰隊資料!')

        connection.close # 關閉連線
      else:
        await message.channel.send(content='資料庫連線失敗!')
    except Error as e:
      print("資料庫連接失敗：", e)
    finally:
      if (connection.is_connected()):
          cursor.close()
          connection.close()
          print("資料庫連線已關閉")

  async def IsAdmin(command):
    if message.author.guild_permissions.administrator:  
      return True
    else:
      await message.channel.send(command+ ' 您的權限不足!')
      return False

  async def IsCaptain(command, connection, server_id, member_id):
    cursor = connection.cursor(prepared=True)
    sql = "SELECT group_serial FROM princess_connect.group_captain WHERE server_id = ? and member_id = ?  LIMIT 0, 1"
    data = (server_id, member_id)
    cursor.execute(sql, data)
    row = cursor.fetchone()
    cursor.close
    if row:
      return row
    else:
      await message.channel.send(command+ ' 您的權限不足!')

  async def IsController(command, connection, server_id):
    group_serial = 0
    now_week = 0
    now_boss = 0
    week_offset = 0
    cursor = connection.cursor(prepared=True)
    sql = "SELECT now_week, now_boss, week_offset, group_serial, controller_role_id FROM princess_connect.group WHERE server_id = ? order by group_serial"
    data = (server_id,)
    cursor.execute(sql, data) # 認證身分
    row = cursor.fetchone()
    while row and group_serial == 0:
      for role in message.author.roles:
        if role.id == row[4]:
          now_week = row[0]
          now_boss = row[1]
          week_offset = row[2]
          group_serial = row[3]
          # TODO 如果一個人多個戰隊的控刀手權限，目前僅會執行編號最小的戰隊
          break
      row = cursor.fetchone()

    try:
      cursor.fetchall()  # fetch (and discard) remaining rows
    except mysql.connector.errors.InterfaceError as ie:
        if ie.msg == 'No result set to fetch from.':
            # no problem, we were just at the end of the result set
            pass
        else:
            raise
    cursor.close
    if group_serial == 0: # 如果是控刀手
      await message.channel.send(command + ' 發生錯誤，您沒有控刀手權限!')

    return ( now_week, now_boss, week_offset, group_serial )

  def IsExistGroup(connection, server_id, group_serial):
    cursor = connection.cursor(prepared=True)
    sql = "SELECT * FROM princess_connect.group WHERE server_id = ? and group_serial = ? limit 0, 1"
    data = (server_id, group_serial)
    cursor.execute(sql, data)
    row = cursor.fetchone()
    cursor.close
    return row

  async def OpenConnection():
    connection = mysql.connector.connect(host=os.getenv('SQLHOST'), database=os.getenv('SQLDB'), user=os.getenv('SQLID'), password=os.getenv('SQLPW'))
    if connection.is_connected():
      return connection
    else:
      await message.channel.send('資料庫連線失敗!')
      return None

  async def CloseConnection(connection):
    if connection.is_connected():
      connection.close
      return True
    else:
      await message.channel.send('連線不存在!!')
      return False

  async def RemindUpdate(connection, server_id):
    cursor = connection.cursor(prepared=True)
    sql = "SELECT upload FROM princess_connect.group WHERE server_id = ? limit 0, 1"
    data = (server_id,)
    cursor.execute(sql, data)
    row = cursor.fetchone()
    cursor.close
    if row:
      if row[0] == 1:
        await message.channel.send('機器人指令有更新囉! 請重新輸入!h以便更新指令表!')
        sql = "UPDATE princess_connect.group SET upload=? WHERE server_id=?"
        data = (0, message.guild.id)
        cursor.execute(sql, data)
        cursor.close
        connection.commit()

    



  # --------------------------------------------------------------------指令部分------------------------------------------------------------------------------------------------------
  try:
    tokens = message.content.split()
    if len(tokens) > 0: # 邊界檢查
      tokens[0] = full2half(tokens[0])

      if tokens[0][0] == '!': # 檢查有無更新訊息
        connection = await OpenConnection()
        if connection:
          await RemindUpdate(connection, message.guild.id)

    # --------------------------------------------------------------------分盟管理 僅限管理者使用------------------------------------------------------------------------------------------------------
    # !建立戰隊  [編號]  ([隊長])
      if tokens[0] == '!建立戰隊' or tokens[0] == '!建立战队' or tokens[0] == '!cg':
        if await IsAdmin(tokens[0]):
          if len(tokens) >= 2:
            if tokens[1].isdigit():
              connection = await OpenConnection()
              if connection:
                group_serial = int(tokens[1])
                if group_serial > 0:

                  # 尋找戰隊有無存在
                  row = IsExistGroup(connection, message.guild.id, group_serial)
                
                  # 查無該戰隊資料，新增一筆，預設1週目1王，除當前週目外，可往後預約4週目
                  if not row: 
                    cursor = connection.cursor(prepared=True)
                    sql = "INSERT INTO princess_connect.group (server_id, group_serial, now_boss, now_week, week_offset, boss_change) VALUES (?, ?, ?, ?, ?, ?)"
                    data = (message.guild.id, group_serial, 1, 1, 4, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) #
                    cursor.execute(sql, data)
                    cursor.close

                    # 尋找指令中,mention的人，並新增進資料庫指派為隊長
                    # 並檢查同一DC有無重複隊長，以避免設定出錯

                    # 檢查成員身分
                    illegal_members = ''
                    captains = []
                    for member in message.mentions:
                      cursor = connection.cursor(prepared=True)
                      sql = "SELECT * FROM princess_connect.group_captain WHERE server_id=? and member_id=? LIMIT 0, 1"
                      data = (message.guild.id, member.id)
                      cursor.execute(sql, data)
                      row = cursor.fetchone()
                      cursor.close
                      if row:
                        illegal_members = illegal_members + member.mention + ' '
                      else:
                        captains.append(member)
                    
                    # 寫入隊長名單
                    legal_members = ''
                    for member in captains:
                      cursor = connection.cursor(prepared=True)
                      sql = "INSERT INTO princess_connect.group_captain (server_id, group_serial, member_id) VALUES (?, ?, ?)"
                      data = (message.guild.id, group_serial, member.id)
                      cursor.execute(sql, data)
                      cursor.close
                      legal_members = legal_members + member.mention + ' '
                
                    connection.commit() # 資料庫存檔
                    connection.close

                    # 列出隊長名單
                    if legal_members == '':
                      if illegal_members == '':
                        await message.channel.send('已新增第' + str(group_serial) + '戰隊!\n尚未設定戰隊隊長，請使用"!戰隊隊長 [數字編號]"設定隊長!')
                      else:
                        await message.channel.send('已新增第' + str(group_serial) + '戰隊!\n因' + illegal_members + '目前已是其他戰隊隊長，故自動取消指派。\n請使用"!戰隊隊長 [數字編號]"設定隊長!')
                    else:
                      if illegal_members == '':
                        await message.channel.send('已新增第' + str(group_serial) + '戰隊!\n隊長為' + legal_members + '。' )
                      else:
                        await message.channel.send('已新增第' + str(group_serial) + '戰隊!\n隊長為' + legal_members + '。\n因' + illegal_members + '目前已是其他戰隊隊長，故自動取消指派。\n')
                  else:
                    await message.channel.send('第' + str(group_serial) + '戰隊已存在!')
                else:
                  await message.channel.send('[編號] 只能是正整數!')

                await CloseConnection(connection)
            else:
              await message.channel.send('[編號] 請使用阿拉伯數字!')
          else:
            await message.channel.send('!建立戰隊 格式錯誤，應為 !建立戰隊 [編號]')
    
            
      # !刪除戰隊  [編號]
      elif tokens[0] == '!刪除戰隊' or tokens[0] == '!删除战队' or tokens[0] == '!dg':
        if await IsAdmin(tokens[0]):
          if len(tokens) == 2:
            if tokens[1].isdigit():
              group_serial = int(tokens[1])
              if group_serial > 0:
                # 尋找戰隊有無存在
                connection = await OpenConnection()
                if connection:
                  row = IsExistGroup(connection, message.guild.id, group_serial)
                  if row: # 找到該戰隊資料，刪除之!
                    # 刪除保留刀表
                    cursor = connection.cursor(prepared=True)
                    sql = "DELETE FROM princess_connect.keep_knifes WHERE server_id = ? and group_serial = ?"
                    data = (message.guild.id, group_serial)
                    cursor.execute(sql, data)
                    cursor.close

                    # 刪除刀表
                    cursor = connection.cursor(prepared=True)
                    sql = "DELETE FROM princess_connect.knifes WHERE server_id = ? and group_serial = ?"
                    data = (message.guild.id, group_serial)
                    cursor.execute(sql, data) 
                    cursor.close
                

                    # 刪除隊長
                    cursor = connection.cursor(prepared=True)
                    sql = "DELETE FROM princess_connect.group_captain WHERE server_id = ? and group_serial = ?"
                    data = (message.guild.id, group_serial)
                    cursor.execute(sql, data) 
                

                    # 刪除戰隊
                    cursor = connection.cursor(prepared=True)
                    sql = "DELETE FROM princess_connect.group WHERE server_id = ? and group_serial = ?"
                    data = (message.guild.id, group_serial)
                    cursor.execute(sql, data) 
                    cursor.close

                    connection.commit() # 資料庫存檔
                    await message.channel.send('已刪除第' + str(group_serial) + '戰隊!')
                  else: 
                    await message.channel.send('第' + str(group_serial) + '戰隊不存在!')

                  await CloseConnection(connection)
              else:
                await message.channel.send('[編號] 只能是正整數!')
            else:
              await message.channel.send('[編號] 請使用阿拉伯數字!')
          else:
            await message.channel.send('!刪除戰隊 格式錯誤，應為 !刪除戰隊 [編號]')


      # !戰隊隊長 [編號] [@成員]
      elif tokens[0] == '!戰隊隊長' or tokens[0] == '!战队队长' or tokens[0] == '!gc':
        if await IsAdmin(tokens[0]):
          if len(tokens) >= 2:
            if tokens[1].isdigit():
              group_serial = int(tokens[1])
              if group_serial > 0:
                # 尋找戰隊有無存在
                connection = await OpenConnection()
                if connection:
                  row = IsExistGroup(connection, message.guild.id, group_serial)
                  if row: # 先刪除現有的隊長，再進行新增
                    # 刪除
                    cursor = connection.cursor(prepared=True)
                    sql = "DELETE FROM princess_connect.group_captain WHERE server_id = ? and group_serial = ?"
                    data = (message.guild.id, group_serial)
                    cursor.execute(sql, data)
                    connection.commit()

                    # 檢查成員身分
                    illegal_members = ''
                    captains = []
                    for member in message.mentions:
                      cursor = connection.cursor(prepared=True)
                      sql = "SELECT * FROM princess_connect.group_captain WHERE server_id=? and member_id=? LIMIT 0, 1"
                      data = (message.guild.id, member.id)
                      cursor.execute(sql, data)
                      row = cursor.fetchone()
                      cursor.close
                      if row:
                        illegal_members = illegal_members + member.mention + ' '
                      else:
                        captains.append(member)
                    
                    # 寫入隊長名單
                    legal_members = ''
                    for member in captains:
                      cursor = connection.cursor(prepared=True)
                      sql = "INSERT INTO princess_connect.group_captain (server_id, group_serial, member_id) VALUES (?, ?, ?)"
                      data = (message.guild.id, group_serial, member.id)
                      cursor.execute(sql, data)
                      cursor.close
                      legal_members = legal_members + member.mention + ' '

                    connection.commit() # 資料庫存檔
                    connection.close

                    # 列出隊長名單
                    if legal_members == '':
                      if illegal_members == '':
                        await message.channel.send('已清除第' + str(group_serial) + '戰隊隊長名單。\n請使用"!戰隊隊長 [數字編號] [@mention]"重新設定隊長!')
                      else:
                        await message.channel.send('已清除第' + str(group_serial) + '戰隊隊長名單。\n因' + illegal_members + '目前已是其他戰隊隊長，故自動取消指派。\n請使用"!戰隊隊長 [數字編號] [@mention]"重新設定隊長!')
                    else:
                      if illegal_members == '':
                        await message.channel.send('第' + str(group_serial) + '戰隊隊長已變更為' + legal_members + '。')
                      else:
                        await message.channel.send('第' + str(group_serial) + '戰隊隊長已變更為' + legal_members + '。\n因' + illegal_members + '目前已是其他戰隊隊長，故自動取消指派。')
                  else: # 查無該戰隊資料，提示錯誤訊息 
                    await message.channel.send('第' + str(group_serial) + '戰隊不存在!')

                  await CloseConnection(connection)
              else:
                await message.channel.send('[編號] 只能是正整數!')
            else: 
              await message.channel.send('[編號] 請使用阿拉伯數字!')
          else:
            await message.channel.send('!戰隊隊長 格式錯誤，應為 !戰隊隊長 [編號] [@mention]')


      # !戰隊列表
      elif tokens[0] == '!戰隊列表' or tokens[0] == '!战队列表' or tokens[0] == '!gl':
        if await IsAdmin(tokens[0]):
          if len(tokens) == 1:
            # 找出該伺服器戰隊
            connection = await OpenConnection()
            if connection:
              connection2 = await OpenConnection()
              if connection2:
                # 列出所有戰隊
                cursor = connection.cursor(prepared=True)
                sql = "SELECT server_id, group_serial, controller_role_id, table_channel_id, sign_channel_id FROM princess_connect.group WHERE server_id = ? order by group_serial"
                data = (message.guild.id, )
                cursor.execute(sql, data)
                row = cursor.fetchone()
              
                count = 0
                embed_msg = Embed(title='戰隊列表', color=0xB37084)
                while row:
                  count = count + 1
                  server_id = row[0]
                  group_serial = row[1]
                  controller_role_id = row[2]
                  table_channel_id = row[3]
                  sign_channel_id = row[4]
                
                  # 找出刀表頻道
                  table_msg = ''
                  if not table_channel_id == None:
                    try:
                      channel = message.guild.get_channel(table_channel_id)
                      table_msg = channel.name
                    except:
                      print("!戰隊列表查無刀表頻道")
                      table_msg = '[N/A]'
                  else:
                    pass

                  # 找出報刀頻道
                  sign_msg = ''
                  if not sign_channel_id == None:
                    try:
                      channel = message.guild.get_channel(sign_channel_id)
                      sign_msg = channel.name
                    except:
                      print("!戰隊列表查無報刀頻道")
                      sign_msg = '[N/A]'
                  else:
                    pass

                  # 找出控刀手
                  controller_role_msg = ''
                  if not controller_role_id == None:
                    try:
                      role = message.guild.get_role(controller_role_id)
                      controller_role_msg = role.name
                    except:
                      print("!戰隊列表查無身分組")
                      controller_role_msg = '[N/A]'
                  else:
                    pass

                  # 找出戰隊隊長
                  captain_msg = ''
                  cursor2 = connection2.cursor(prepared=True)
                  sql = "SELECT member_id FROM princess_connect.group_captain WHERE server_id = ? and group_serial = ?"
                  data = (server_id,group_serial)
                  cursor2.execute(sql, data)
                  inner_row = cursor2.fetchone()
                  captain_msg = ''
                  while inner_row:
                    member_name = await get_nick_name(inner_row[0])
                    captain_msg = captain_msg + member_name + ', '
                    inner_row = cursor2.fetchone()
                  cursor2.close

                  # 組裝
                  msg_send = ''
                  if table_msg == '':
                    msg_send = msg_send + '刀表頻道:尚未指派!\n'
                  else:
                    msg_send = msg_send + '刀表頻道:'+ table_msg +'\n'

                  if sign_msg == '':
                    msg_send = msg_send + '刀表頻道:尚未指派!\n'
                  else:
                    msg_send = msg_send + '刀表頻道:'+ sign_msg +'\n'

                  if controller_role_msg == '':
                    msg_send = msg_send + '控刀手身分組:尚未指派!\n'
                  else:
                    msg_send = msg_send + '控刀手身分組:'+ controller_role_msg +'\n'

                  if captain_msg == '':
                    msg_send = msg_send + '隊長:尚未指派!\n'
                  else:
                    msg_send = msg_send + '隊長:' + captain_msg + '\n'

                  embed_msg.add_field(name='第' + str(group_serial) + '戰隊:', value=msg_send, inline=False)
                  row = cursor.fetchone()
              
                cursor.close
                if count == 0: # 查無資料，新增資料
                  await message.channel.send('目前沒有戰隊!')
                else:
                  await message.channel.send(embed = embed_msg)

                await CloseConnection(connection2)

              await CloseConnection(connection)
          else:
            await message.channel.send('!戰隊列表 格式錯誤，應為 !戰隊列表')     


      # --------------------------------------------------------------------戰隊管理 僅限戰隊隊長使用------------------------------------------------------------------------------------------------------
      # !設定控刀手身分組 [身分組]
      elif tokens[0] == '!控刀手身分組' or tokens[0] == '!控刀手身分组' or tokens[0] == '!cr':
        if len(tokens) == 2:
          connection = await OpenConnection()
          if connection:
            row = await IsCaptain(tokens[0], connection, message.guild.id, message.author.id)
            if row:
              group_serial = int(row[0])
              if len(message.role_mentions) == 1:
                # 檢查有無重複
                cursor = connection.cursor(prepared=True)
                sql = "SELECT group_serial FROM princess_connect.group WHERE server_id=? and controller_role_id =? LIMIT 0, 1"
                data = (message.guild.id, message.role_mentions[0].id)
                cursor.execute(sql, data)
                row = cursor.fetchone()
                cursor.close
                if not row:
                  cursor = connection.cursor(prepared=True)
                  sql = "UPDATE princess_connect.group SET controller_role_id = ? WHERE server_id = ? and group_serial = ? "
                  data = (message.role_mentions[0].id, message.guild.id, group_serial)
                  cursor.execute(sql, data)
                  cursor.close
                  connection.commit()
                  await message.channel.send(message.role_mentions[0].mention + '身分組已指派為第' + str(group_serial) + '戰隊控刀手!')
                else:
                  if not int(row[0]) == group_serial:
                    await message.channel.send('控刀手身分組與其他戰隊重複，請重新設定!')
                  else: # 指派一樣的身分組，SQL不處理但再次顯示成功訊息
                    await message.channel.send(message.role_mentions[0].mention + '身分組已指派為第' + str(group_serial) + '戰隊控刀手!')
              elif len(message.role_mentions) == 0:
                await message.channel.send('需指派一個身分組，設定失敗!')
              else:
                await message.channel.send('只能指派一個身分組，設定失敗!')
            
            await CloseConnection(connection)
        else:
          await message.channel.send('!控刀手身分组 格式錯誤，應為 !控刀手身分组 [@身分組]')
    
          
      #  !刀表在此
      elif tokens[0] == '!刀表在此' or tokens[0] == '!刀表在此' or tokens[0] == '!tc':
        if len(tokens) == 1:
          connection = await OpenConnection()
          if connection:
            row = await IsCaptain(tokens[0], connection, message.guild.id, message.author.id)
            if row:
              group_serial = int(row[0])
              cursor = connection.cursor(prepared=True)
              sql = "SELECT group_serial FROM princess_connect.group WHERE server_id = ? and table_channel_id = ? and group_serial <> ? limit 0, 1"
              data = (message.guild.id, message.channel.id, group_serial)
              cursor.execute(sql, data)
              row = cursor.fetchone()
              cursor.close
              if not row:
                cursor = connection.cursor(prepared=True)
                sql = "SELECT table_style FROM princess_connect.group WHERE server_id = ? and group_serial = ? limit 0, 1"
                data = (message.guild.id, group_serial)
                cursor.execute(sql, data)
                row = cursor.fetchone()
                cursor.close
                if row :
                  if row[0] == 0:
                    embed_msg = Embed(description="初始化刀表中!",color=0xD98B99)
                    table_message = await message.channel.send(embed = embed_msg)
                    embed_msg = Embed(description="初始化暫存刀表中!",color=0xD9ACA3)
                    knife_pool_message = await message.channel.send(embed = embed_msg)
                  else:
                    msg = "初始化刀表中!"
                    table_message = await message.channel.send(msg)
                    msg = "初始化暫存刀表中!"
                    knife_pool_message = await message.channel.send(msg)

                  # 寫入資料庫
                  cursor = connection.cursor(prepared=True)
                  sql = "UPDATE princess_connect.group SET table_channel_id = ? ,table_message_id = ?, knife_pool_message_id=? WHERE server_id = ? and group_serial = ? "
                  data = (message.channel.id, table_message.id, knife_pool_message.id, message.guild.id, group_serial)
                  cursor.execute(sql, data)
                  cursor.close
                  connection.commit()
                  await Update(message.guild.id, group_serial)
                else:
                  await message.channel.send('查無戰隊資料!') 
              else:
                await message.channel.send('這裡是第'+ str(row[0]) +'戰隊的刀表頻道，請重新選擇!')

            await CloseConnection(connection)
        else:
          await message.channel.send('!刀表在此 格式錯誤，應為 !刀表在此')


      #  !報刀在此
      elif tokens[0] == '!報刀在此' or tokens[0] == '!报刀在此' or tokens[0] == '!sc':
        if len(tokens) == 1:
          connection = await OpenConnection()
          if connection:
            row = await IsCaptain(tokens[0], connection, message.guild.id, message.author.id)
            if row:
              group_serial = int(row[0])
              cursor = connection.cursor(prepared=True)
              sql = "SELECT group_serial FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? and group_serial <> ? limit 0, 1"
              data = (message.guild.id, message.channel.id, group_serial)
              cursor.execute(sql, data)
              row = cursor.fetchone()
              cursor.close
              if not row:
                # 寫入資料庫
                cursor = connection.cursor(prepared=True)
                sql = "UPDATE princess_connect.group SET sign_channel_id = ? WHERE server_id = ? and group_serial = ? "
                data = (message.channel.id, message.guild.id, group_serial)
                cursor.execute(sql, data)
                cursor.close
                connection.commit()
                await message.channel.send('報刀是吧，了解!')
              else:
                await message.channel.send('這裡是第'+ str(row[0]) +'戰隊的報刀頻道，請重新選擇!')
            
            await CloseConnection(connection)
        else:
          await message.channel.send('!報刀在此 格式錯誤，應為 !報刀在此')


      #  !預約週目控制 [幾週]
      elif tokens[0] == '!提前週目' or tokens[0] == '!提前周目' or tokens[0] == '!wo':
        connection = await OpenConnection()
        if connection:
          row = await IsCaptain(tokens[0], connection, message.guild.id, message.author.id)
          if row:
            if len(tokens) == 2:
              if tokens[1].isdigit():
                week_offset = int(tokens[1])
                if 0 <= week_offset and week_offset <= 10:
                  # 寫入資料庫
                  cursor = connection.cursor(prepared=True)
                  sql = "UPDATE princess_connect.group SET week_offset = ? WHERE server_id = ? and group_serial = ? "
                  data = (week_offset, message.guild.id, row[0])
                  cursor.execute(sql, data)
                  cursor.close
                  connection.commit()
                  await message.channel.send('現在可以往後預約'+ str(week_offset) +'個週目囉!')
                  await Update(message.guild.id, row[0])
                elif week_offset < 0:
                  await message.channel.send('[幾週目]只能是正整數喔!')
                else:
                  await message.channel.send('真步記不起來，你提早太多了，最多10週!')
              else:
                await message.channel.send('請使用阿拉伯數字填寫可以向後預約幾個週目!')
            else:
              await message.channel.send('!提前週目 格式錯誤，應為 !提前週目 [幾週目]')

          await CloseConnection(connection)


      #  !清除刀表 [幾週]
      elif tokens[0] == '!清除刀表' or tokens[0] == '!清除刀表' or tokens[0] == '!ct':
        if len(tokens) == 1:
          connection = await OpenConnection()
          if connection:
            row = await IsCaptain(tokens[0], connection, message.guild.id, message.author.id)
            if row:
              group_serial = row[0]
              # 刪除保留刀表
              cursor = connection.cursor(prepared=True)
              sql = "DELETE FROM princess_connect.keep_knifes WHERE server_id = ? and group_serial = ?"
              data = (message.guild.id, group_serial)
              cursor.execute(sql, data)
              cursor.close

              # 刪除刀表
              cursor = connection.cursor(prepared=True)
              sql = "DELETE FROM princess_connect.knifes WHERE server_id = ? and group_serial = ?"
              data = (message.guild.id, group_serial)
              cursor.execute(sql, data) 
              cursor.close

              # 重設boss次序
              cursor = connection.cursor(prepared=True)
              sql = "UPDATE princess_connect.group SET now_week='1', now_boss='1' WHERE server_id = ? and group_serial=?"
              data = (message.guild.id, group_serial)
              cursor.execute(sql, data)
              cursor.close
              connection.commit()
              await message.channel.send('第'+ str(group_serial) +'戰隊刀表被真步吃光光拉!')
              await Update(message.guild.id, group_serial) # 更新刀表

            await CloseConnection(connection)
        else:
          await message.channel.send('!清除刀表 格式錯誤，應為 !清除刀表')


      elif tokens[0] == '!匯出刀表' or tokens[0] == '!汇出刀表' or tokens[0] == '!e':
        if len(tokens) == 1:
          connection = await OpenConnection()
          if connection:
            row = await IsCaptain(tokens[0], connection, message.guild.id, message.author.id)
            if row:
              group_serial = row[0]
              server_id = message.guild.id
            
              msg = [['序號', '週目', 'BOSS', '隊員識別碼', '隊員姓名', '備註', '時間']]

              # 獲取刀表
              cursor = connection.cursor(prepared=True)
              sql = "SELECT member_id, week, boss, comment, timestamp FROM princess_connect.knifes WHERE server_id = ? and group_serial = ? order by week, boss, serial_number"
              data = (server_id, group_serial)
              cursor.execute(sql, data)
              row = cursor.fetchone()
              index = 1
              while row:
                nick_name = await get_nick_name(row[0])
                msg.append([index,row[1] ,row[2] ,row[0] ,nick_name, row[3], row[4]])
                row = cursor.fetchone()
                index = index +1
              cursor.close()
            
              filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '_' + str(server_id) + '_request.csv' # 檔案名稱

              # 寫檔
              with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile) # 建立 CSV 檔寫入器
                writer.writerows(msg) # 寫入欄位

              # 傳送私人訊息
              await message.author.send('咕嚕靈波，你要的刀表來囉!')
              await message.author.send(file=discord.File(filename))
              await message.channel.send('刀表匯出成功!')

              os.remove(filename) # 移除檔案

            await CloseConnection(connection)
        else:
          await message.channel.send('!匯出刀表 格式錯誤，應為 !匯出刀表')


      elif tokens[0] == '!刀表樣式' or tokens[0] == '!刀表样式' or tokens[0] == '!ts':
        connection = await OpenConnection()
        if connection:
          server_id = message.guild.id
          row = await IsCaptain(tokens[0], connection, server_id, message.author.id)
          if row:
            group_serial = row[0]
            if len(tokens) == 2:
              if tokens[1].isdigit():
                style = int(tokens[1])
                if  style == 0 or style == 1:
                  # 查詢刀表訊息、保留刀訊息
                  cursor = connection.cursor(prepared=True)
                  sql = "SELECT table_channel_id, table_message_id, knife_pool_message_id FROM princess_connect.group WHERE server_id = ? and group_serial = ? LIMIT 0, 1"
                  data = (server_id, group_serial)
                  cursor.execute(sql, data)
                  row = cursor.fetchone()
                  cursor.close
                  if row:
                    table_channel_id = row[0]
                    table_message_id = row[1]
                    knife_pool_message_id = row[2]
                    # 取得訊息物件並刪除
                    try:
                      channel = message.guild.get_channel(table_channel_id)
                      if table_message_id:
                        msg_obj = await channel.fetch_message(table_message_id)
                        await msg_obj.delete()
                      if knife_pool_message_id:
                        msg_obj = await channel.fetch_message(knife_pool_message_id)
                        await msg_obj.delete()
                    
                      # 產生新訊息物件並寫入資料庫
                      table_message = None
                      knife_pool_message = None
                      if style == 0:
                        embed_msg = Embed(description="初始化刀表中!",color=0xD98B99)
                        table_message = await channel.send(embed = embed_msg)
                        embed_msg = Embed(description="初始化暫存刀表中!",color=0xD9ACA3)
                        knife_pool_message = await channel.send(embed = embed_msg)
                        await message.channel.send('已切換為Embed樣式!')
                      else:
                        msg = "初始化刀表中!"
                        table_message = await channel.send(msg)
                        msg = "初始化暫存刀表中!"
                        knife_pool_message = await channel.send(msg)
                        await message.channel.send('已切換為Text樣式!')
                    
                      # 寫入資料庫
                      cursor = connection.cursor(prepared=True)
                      sql = "UPDATE princess_connect.group SET table_channel_id = ? ,table_message_id = ?, knife_pool_message_id=?, table_style = ? WHERE server_id = ? and group_serial = ? "
                      data = (channel.id, table_message.id, knife_pool_message.id, style, server_id, group_serial)
                      cursor.execute(sql, data)
                      cursor.close
                      connection.commit()
                      await Update(message.guild.id, group_serial)
                    except:
                      await message.channel.send('刀表訊息已被移除，請重新設定刀表頻道!')
                  else:
                    await message.channel.send('查無戰隊資料!')
                else:
                  await message.channel.send('只能是0或1!(0:Embed, 1:Text)')
              else:
                await message.channel.send('請使用阿拉伯數字0或1!')
            else:
              await message.channel.send('!刀表樣式 格式錯誤，應為 !刀表樣式 [樣式代號]')
         
          await CloseConnection(connection)
      

      # --------------------------------------------------------------------出刀管理 僅限控刀手使用------------------------------------------------------------------------------------------------------
      # !移動 [週目] [幾王] [第幾刀] 到 [週目] [幾王]
      elif tokens[0] == '!移動' or tokens[0] == '!移动' or tokens[0] == '!m':
        group_serial = 0
        now_week = 0
        now_boss = 0
        week_offset = 0
        connection = await OpenConnection()
        if connection:
          ( now_week, now_boss, week_offset, group_serial ) = await IsController(tokens[0], connection, message.guild.id) # check身分，並找出所屬組別
          if not group_serial == 0: # 如果是控刀手
            if len(tokens) == 6:
              if tokens[1].isdigit() and tokens[2].isdigit() and tokens[3].isdigit() and tokens[4].isdigit() and tokens[5].isdigit():
                source_week = int(tokens[1])
                source_boss = int(tokens[2])
                source_knife = int(tokens[3])
                destination_week = int(tokens[4])
                destination_boss = int(tokens[5])
                if Check_week((now_week, now_boss, week_offset), source_week) and Check_week((now_week, now_boss, week_offset), destination_week):
                  if Check_boss((now_week, now_boss, week_offset), source_week, source_boss) and Check_boss((now_week, now_boss, week_offset), destination_week, destination_boss):
                    # 尋找要刪除刀的序號
                    delete_index = 0
                    cursor = connection.cursor(prepared=True)
                    sql = "SELECT serial_number,server_id, group_serial, boss, member_id, comment from princess_connect.knifes where server_id=? and group_serial=? and week=? and boss=? order by serial_number limit ?,1"
                    data = (message.guild.id, group_serial, source_week, source_boss, source_knife-1)
                    cursor.execute(sql, data)
                    row = cursor.fetchone()
                    cursor.close()
                    if row:
                      # 寫入刀表
                      cursor = connection.cursor(prepared=True)
                      sql = "INSERT INTO princess_connect.knifes (server_id, group_serial, member_id, week, boss, comment, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)"
                      data = (row[1], row[2], row[4], destination_week ,destination_boss, row[5], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                      cursor.execute(sql, data)
                      cursor.close()


                      # 刪除保留刀表
                      cursor = connection.cursor(prepared=True)
                      sql = "DELETE from princess_connect.knifes where serial_number=?"
                      data = (row[0],)
                      cursor.execute(sql, data)
                      cursor.close()
                      connection.commit()
                      await message.channel.send('第' + str(source_week) + '週目' + str(source_boss) + '王，移動完成!')
                      await Update(message.guild.id, group_serial) # 更新刀表
                    else:
                      await message.channel.send('該刀不存在喔!')
                  else:
                    await message.channel.send('該王不存在喔!')
                else:
                  await message.channel.send('該週目不存在喔!')
              else:
                await message.channel.send('[第幾刀] [週目] [王] 請使用阿拉伯數字!')
            else:
              await message.channel.send('!移動 格式錯誤，應為 !移動 [週目] [boss] [第幾刀] [新週目] [新boss]')
          else:
            await message.channel.send('您沒有控刀手權限!')
          connection.close # 關閉資料庫
        else:
          await message.channel.send('資料庫連線失敗!')


      # !刪除 [週目] [幾王] [第幾刀]
      elif tokens[0] == '!刪除' or tokens[0] == '!删除' or tokens[0] == '!fd':
        # check身分，並找出所屬組別
        group_serial = 0
        now_week = 0
        now_boss = 0
        week_offset = 0
        connection = await OpenConnection()
        if connection:
          ( now_week, now_boss, week_offset, group_serial ) = await IsController(tokens[0], connection, message.guild.id)
          if not group_serial == 0: # 如果是是控刀手
            if len(tokens) == 4:
              if tokens[1].isdigit() and tokens[2].isdigit() and tokens[3].isdigit():
                week = int(tokens[1])
                boss = int(tokens[2])
                knife = int(tokens[3])
                if Check_week((now_week, now_boss, week_offset), week):
                  if Check_boss((now_week, now_boss, week_offset), week,boss):
                    # 尋找要刪除刀的序號
                    delete_index = 0
                    cursor = connection.cursor(prepared=True)
                    sql = "SELECT serial_number,server_id, group_serial, boss, member_id, comment from princess_connect.knifes where server_id=? and group_serial=? and week=? and boss=? order by serial_number limit ?,1"
                    data = (message.guild.id, group_serial, week, boss, knife-1)
                    cursor.execute(sql, data)
                    row = cursor.fetchone()
                    cursor.close()
                    if row:
                      # 刪除刀表
                      cursor = connection.cursor(prepared=True)
                      sql = "DELETE from princess_connect.knifes where serial_number=?"
                      data = (row[0],)
                      cursor.execute(sql, data)
                      cursor.close()
                      connection.commit()
                      await message.channel.send('刪除成功!')
                      await Update(message.guild.id, group_serial) # 更新刀表
                    else:
                      await message.channel.send('該刀不存在喔!')
                  else:
                    await message.channel.send('該王不存在喔!')
                else:
                  await message.channel.send('該週目不存在喔!')
              else:
                await message.channel.send('[週目] [王] [第幾刀] 請使用阿拉伯數字!')
            else:
              await message.channel.send('!刪除 格式錯誤，應為 !刪除 [週目] [王] [第幾刀]')
          else:
            await message.channel.send('您沒有控刀手權限!')
          connection.close # 關閉資料庫
        else:
          await message.channel.send('資料庫連線失敗!')


      # !幫報 [周目] [幾王] [註解] [mention]
      elif tokens[0] == '!幫報' or tokens[0] == '!帮报' or tokens[0] == '!hp':
        # check身分，並找出所屬組別
        group_serial = 0
        now_week = 0
        now_boss = 0
        week_offset = 0
        connection = await OpenConnection()
        if connection:
          ( now_week, now_boss, week_offset, group_serial ) = await IsController(tokens[0], connection, message.guild.id)
          if not group_serial == 0: # 如果是是控刀手
            if len(tokens) == 5:
              if tokens[1].isdigit() and tokens[2].isdigit():
                week = int(tokens[1])
                boss = int(tokens[2])
                comment = tokens[3]
                if message.mentions:
                  if Check_week((now_week, now_boss, week_offset), week):
                    if Check_boss((now_week, now_boss, week_offset), week,boss):
                      # 新增進刀表
                      cursor = connection.cursor(prepared=True)
                      sql = "INSERT INTO princess_connect.knifes (server_id, group_serial, week, boss, member_id, comment, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)"
                      data = (message.guild.id, group_serial, week, boss, message.mentions[0].id, comment ,datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                      cursor.execute(sql, data)
                      cursor.close
                      connection.commit()
                      await message.channel.send('幫報完成! 第' + str(week) + '週目' + str(boss) + '王，備註:' + comment + '。')
                      await Update(message.guild.id, group_serial) # 更新刀表
                    else:
                      await message.channel.send('該王不存在喔!')
                  else:
                    await message.channel.send('該週目不存在喔!')
                else:
                  await message.channel.send('請mention你要幫報的人喔!')
              else:
                await message.channel.send('[週目] [王] 請使用阿拉伯數字!')
            else:
              await message.channel.send('!幫報 格式錯誤，應為 !幫報 [週目] [王] [註解] [@mention]')
          else:
            await message.channel.send('您沒有控刀手權限!')
          connection.close # 關閉資料庫
        else:
          await message.channel.send('資料庫連線失敗!')


      #!幫報保留刀 [幾王] [註解] [mention]
      elif tokens[0] == '!幫報保留刀' or tokens[0] == '!帮报保留刀' or tokens[0] == '!hkp':
       # check身分，並找出所屬組別
        group_serial = 0
        now_week = 0
        now_boss = 0
        week_offset = 0
        connection = await OpenConnection()
        if connection:
          ( now_week, now_boss, week_offset, group_serial ) = await IsController(tokens[0], connection, message.guild.id)
          if not group_serial == 0: # 如果是是控刀手
            if len(tokens) == 4:
              if tokens[1].isdigit():
                if int(tokens[1]) > 0 and int(tokens[1]) < 6:
                  if message.mentions:
                    # 寫入保留刀表
                    cursor = connection.cursor(prepared=True)
                    sql = "INSERT INTO princess_connect.keep_knifes (server_id, group_serial, member_id, boss, comment) VALUES (?, ?, ?, ?, ?)"
                    data = (message.guild.id, group_serial, message.mentions[0].id, int(tokens[1]), tokens[2])
                    cursor.execute(sql, data)
                    cursor.close()
                    connection.commit()
                    await message.channel.send(tokens[1] + '王，備註:' + tokens[2] + '，**保留刀**報刀成功!')
                    await Update(message.guild.id, group_serial) # 更新刀表
                  else:
                    await message.channel.send('請mention你要幫報**保留刀**的人喔!')
                else:
                  await message.channel.send('該王不存在喔!')
              else:
                await message.channel.send('[幾王]請使用阿拉伯數字!')
            else:
              await message.channel.send('!幫報保留刀 格式錯誤，應為 !幫報保留刀 [王] [註解] [mention]')
          else:
            pass #非指定頻道 不反應
          connection.close
        else:
          await message.channel.send('資料庫連線失敗!')
    

      #!刪除保留刀 [第幾刀]
      elif tokens[0] == '!刪除保留刀' or tokens[0] == '!删除保留刀' or tokens[0] == '!fdkp':
        # check身分，並找出所屬組別
        group_serial = 0
        now_week = 0
        now_boss = 0
        week_offset = 0
        connection = await OpenConnection()
        if connection:
          ( now_week, now_boss, week_offset, group_serial ) = await IsController(tokens[0], connection, message.guild.id)
          if not group_serial == 0: # 如果是是控刀手
            if len(tokens) == 2:
              if tokens[1].isdigit():
                index = int(tokens[1]) # TODO check index 不可為負數

                # 尋找要刪除刀的序號
                cursor = connection.cursor(prepared=True)
                sql = "SELECT serial_number,member_id from princess_connect.keep_knifes where server_id=? and group_serial=? order by boss limit ?,1"
                data = (message.guild.id, group_serial, index-1)
                cursor.execute(sql, data)
                row = cursor.fetchone()
                cursor.close()
                if row:
                  cursor = connection.cursor(prepared=True)
                  sql = "DELETE from princess_connect.keep_knifes where serial_number=?"
                  data = (row[0],)
                  row = cursor.execute(sql, data)
                  cursor.close()
                  connection.commit()
                  await message.channel.send('刪除保留刀成功!')
                  await Update(message.guild.id, group_serial) # 更新刀表   
                else:
                  await message.channel.send('該保留刀不存在喔!') 
              else:
                await message.channel.send('[第幾刀]請使用阿拉伯數字!')
            else:
              await message.channel.send('!刪除保留刀 格式錯誤，應為 !刪除保留刀 [第幾刀]')
          else:
            await message.channel.send('您沒有控刀手權限!')
        else:
          await message.channel.send('資料庫連線失敗!')


      # !設定 [週目] [幾王]
      elif tokens[0] == '!設定' or tokens[0] == '!设定' or tokens[0] == '!s':
        # check身分，並找出所屬組別
        group_serial = 0
        now_week = 0
        now_boss = 0
        week_offset = 0
        connection = await OpenConnection()
        if connection:
          ( now_week, now_boss, week_offset, group_serial ) = await IsController(tokens[0], connection, message.guild.id)
          if not group_serial == 0: # 如果是是控刀手
            if len(tokens) == 3:
              if tokens[1].isdigit() and tokens[2].isdigit():
                if int(tokens[1]) > 0 and int(tokens[2]) > 0 and int(tokens[2]) < 6: #週目大於0 0<王<6
                  cursor = connection.cursor(prepared=True)
                  sql = "UPDATE princess_connect.group SET now_week=?, now_boss=? WHERE server_id = ? and group_serial=? order by group_serial"
                  data = (int(tokens[1]),int(tokens[2]),message.guild.id, group_serial)
                  cursor.execute(sql, data)
                  cursor.close
                  connection.commit()
                  await message.channel.send('已切換至' + tokens[1] + '週目' + tokens[2] + '王!')
                  await Update(message.guild.id, group_serial) # 更新刀表
                else:
                  await message.channel.send('週目或王的數字打錯囉!')
              else:
                await message.channel.send('[週目] [王] 請使用阿拉伯數字!')
            else:
              await message.channel.send('!設定 格式錯誤，應為 !設定 [週目] [王]!')
          else:
            await message.channel.send('您沒有控刀手權限!')
          connection.close # 關閉資料庫
        else:
          await message.channel.send('資料庫連線失敗!')


      # --------------------------------------------------------------------一般成員 僅限報刀頻道使用------------------------------------------------------------------------------------------------------          
      #報刀指令 !預約 [周目] [幾王] [註解]
      elif tokens[0] == '!預約' or tokens[0] == '!预约' or tokens[0] == '!p':
        # check頻道，並找出所屬組別
        group_serial = 0
        
        connection = await OpenConnection()
        if connection:
          cursor = connection.cursor(prepared=True)
          sql = "SELECT now_week, now_boss, week_offset, group_serial FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? order by group_serial limit 0, 1"
          data = (message.guild.id, message.channel.id)
          cursor.execute(sql, data) # 認證身分
          row = cursor.fetchone()
          cursor.close
          if row:
            group_serial = row[3]
            if len(tokens) == 4:
              if tokens[1].isdigit() and tokens[2].isdigit() :
                week = int(tokens[1])
                boss = int(tokens[2])
                comment = tokens[3]
                if Check_week((row[0], row[1], row[2]), week):
                  if Check_boss((row[0], row[1], row[2]),week, boss):
                    # 新增刀
                    cursor = connection.cursor(prepared=True)
                    sql = "INSERT INTO princess_connect.knifes (server_id, group_serial, week, boss, member_id, comment, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)"
                    data = (message.guild.id, group_serial, week, boss, message.author.id, comment ,datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    cursor.execute(sql, data)
                    cursor.close
                    connection.commit()
                    await message.channel.send('第' + str(week) + '週目' + str(boss) + '王，備註:' + comment + '，報刀成功!')
                    await Update(message.guild.id, group_serial) # 更新刀表
                  else:
                    await message.channel.send('該王不存在喔!')
                else:
                  await message.channel.send('該週目不存在喔!')
              else:
                await message.channel.send('[週目] [王]請使用阿拉伯數字!')
            else:
              await message.channel.send('!預約 格式錯誤，應為 !預約 [週目] [王] [註解]')
          else:
            pass #非指定頻道 不反應
          await CloseConnection(connection)


      #!取消報刀  !取消預約 [周目] [幾王] [第幾刀]
      elif tokens[0] == '!取消預約' or tokens[0] == '!取消预约' or tokens[0] == '!cp':
        group_serial = 0
        connection = await OpenConnection()
        if connection:
          cursor = connection.cursor(prepared=True)
          sql = "SELECT now_week, now_boss, week_offset, group_serial FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? order by group_serial limit 0, 1"
          data = (message.guild.id, message.channel.id)
          cursor.execute(sql, data) # 認證身分
          row = cursor.fetchone()
          cursor.close
          if row:
            group_serial = row[3]
            if len(tokens) == 4:
              if tokens[1].isdigit() and tokens[2].isdigit() and tokens[3].isdigit():
                week = int(tokens[1])
                boss = int(tokens[2])
                index = int(tokens[3]) # TODO check index 不可為負數
                if Check_week((row[0], row[1], row[2]), week):
                  if Check_boss((row[0], row[1], row[2]), week,boss):
                    # 尋找要刪除刀的序號
                    delete_index = 0
                    cursor = connection.cursor(prepared=True)
                    sql = "SELECT serial_number,member_id from princess_connect.knifes where server_id=? and group_serial=? and week=? and boss=? order by serial_number limit ?,1"
                    data = (message.guild.id, group_serial, week, boss,index-1)
                    cursor.execute(sql, data)
                    row = cursor.fetchone()
                    cursor.close()
                    if row:
                      if message.author.id == row[1]:
                        cursor = connection.cursor(prepared=True)
                        sql = "DELETE from princess_connect.knifes where serial_number=?"
                        data = (row[0],)
                        row = cursor.execute(sql, data)
                        cursor.close()
                        connection.commit()
                        await message.channel.send('取消成功!')
                        await Update(message.guild.id, group_serial) # 更新刀表
                      else:
                        await message.channel.send('您並非該刀主人喔!')
                    else:
                      await message.channel.send('該刀不存在喔!')
                  else:
                    await message.channel.send('該王不存在喔!')
                else:
                  await message.channel.send('該週目不存在喔!')
              else:
                await message.channel.send('[週目] [王] [第幾刀]請使用阿拉伯數字!')
            else:
              await message.channel.send('!取消預約 格式錯誤，應為 !取消預約 [週目] [王] [第幾刀]')
          else:
            pass #非指定頻道 不反應
          await CloseConnection(connection)
        
      
      elif tokens[0] == '!報保留刀' or tokens[0] == '!报保留刀' or tokens[0] == '!kp':
        # check頻道，並找出所屬組別
        group_serial = 0
        connection = await OpenConnection()
        if connection:
          cursor = connection.cursor(prepared=True)
          sql = "SELECT group_serial FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? order by group_serial limit 0, 1"
          data = (message.guild.id, message.channel.id)
          cursor.execute(sql, data) # 認證身分
          row = cursor.fetchone()
          cursor.close
          if row:
            group_serial = row[0]
            if len(tokens) == 3:
              if tokens[1].isdigit():
                if int(tokens[1]) > 0 and int(tokens[1]) < 6:
                  # 寫入保留刀表
                  cursor = connection.cursor(prepared=True)
                  sql = "INSERT INTO princess_connect.keep_knifes (server_id, group_serial, member_id, boss, comment) VALUES (?, ?, ?, ?, ?)"
                  data = (message.guild.id, group_serial, message.author.id, int(tokens[1]), tokens[2])
                  cursor.execute(sql, data)
                  cursor.close()
                  connection.commit()
                  await message.channel.send(tokens[1] + '王，備註:' + tokens[2] + '，**保留刀**報刀成功!')
                  await Update(message.guild.id, group_serial) # 更新刀表
                else:
                  await message.channel.send('該王不存在喔!')
              else:
                await message.channel.send('[幾王]請使用阿拉伯數字!')
            else:
              await message.channel.send('!報保留刀 格式錯誤，應為 !報保留刀 [王] [註解]')
          else:
            pass #非指定頻道 不反應
          await CloseConnection(connection)
        
      #!使用保留刀 [第幾刀] [週目] [boss]
      elif tokens[0] == '!使用保留刀' or tokens[0] == '!使用保留刀' or tokens[0] == '!ukp':
        group_serial = 0
        connection = await OpenConnection()
        if connection:
          cursor = connection.cursor(prepared=True)
          sql = "SELECT  now_week, now_boss, week_offset, group_serial FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? order by group_serial limit 0, 1"
          data = (message.guild.id, message.channel.id)
          cursor.execute(sql, data) # 認證身分
          row = cursor.fetchone()
          cursor.close
          if row:
            group_serial = row[3]
            if len(tokens) == 4:
              if tokens[1].isdigit() and tokens[2].isdigit() and tokens[3].isdigit():
                index = int(tokens[1]) # TODO check index 不可為負數
                week = int(tokens[2])
                boss = int(tokens[3])
                if Check_week((row[0], row[1], row[2]), week):
                  if Check_boss((row[0], row[1], row[2]),week, boss):  
                    cursor = connection.cursor(prepared=True)
                    sql = "SELECT serial_number, member_id, comment from princess_connect.keep_knifes where server_id=? and group_serial=? order by boss limit ?,1"
                    data = (message.guild.id, group_serial, index-1)
                    cursor.execute(sql, data)
                    row = cursor.fetchone()
                    cursor.close()
                    if row:
                      if message.author.id == row[1]:
                        # 新增刀
                        cursor = connection.cursor(prepared=True)
                        sql = "INSERT INTO princess_connect.knifes (server_id, group_serial, week, boss, member_id, comment, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)"
                        data = (message.guild.id, group_serial, week, boss, row[1], row[2] ,datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        cursor.execute(sql, data)
                        cursor.close

                        # 刪除刀
                        cursor = connection.cursor(prepared=True)
                        sql = "DELETE from princess_connect.keep_knifes where serial_number=?"
                        data = (row[0],)
                        cursor.execute(sql, data)
                        cursor.close()

                        connection.commit()
                        await message.channel.send('第' + str(week) + '週目' + str(boss) + '王，備註:' + row[2] + '，報刀成功!')
                        await Update(message.guild.id, group_serial) # 更新刀表
                      else:
                        await message.channel.send('您並非該刀主人喔!')
                    else:
                      await message.channel.send('該刀不存在喔!')   
                  else:
                    await message.channel.send('該王不存在喔!')
                else:
                  await message.channel.send('該週目不存在喔!')
              else:
                await message.channel.send('[第幾刀] [週目] [boss]請使用阿拉伯數字!')
            else:
              await message.channel.send('!使用保留刀 格式錯誤，應為 !使用保留刀 [第幾刀] [週目] [boss]')
          else:
            pass #非指定頻道 不反應
          await CloseConnection(connection)


      #!取消保留刀 [第幾刀]
      elif tokens[0] == '!取消保留刀' or tokens[0] == '!取消保留刀' or tokens[0] == '!ckp':
        group_serial = 0
        connection = await OpenConnection()
        if connection:
          cursor = connection.cursor(prepared=True)
          sql = "SELECT  now_week, now_boss, week_offset, group_serial FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? order by group_serial limit 0, 1"
          data = (message.guild.id, message.channel.id)
          cursor.execute(sql, data) # 認證身分
          row = cursor.fetchone()
          cursor.close
          if row:
            group_serial = row[3]
            if len(tokens) == 2:
              if tokens[1].isdigit():
                index = int(tokens[1]) # TODO check index 不可為負數

                # 尋找要刪除刀的序號
                cursor = connection.cursor(prepared=True)
                sql = "SELECT serial_number,member_id from princess_connect.keep_knifes where server_id=? and group_serial=? order by boss limit ?,1"
                data = (message.guild.id, group_serial, index-1)
                cursor.execute(sql, data)
                row = cursor.fetchone()
                cursor.close()
                if row:
                  if message.author.id == row[1]:
                    cursor = connection.cursor(prepared=True)
                    sql = "DELETE from princess_connect.keep_knifes where serial_number=?"
                    data = (row[0],)
                    row = cursor.execute(sql, data)
                    cursor.close()
                    connection.commit()
                    await message.channel.send('取消保留刀成功!')
                    await Update(message.guild.id, group_serial) # 更新刀表
                  else:
                    await message.channel.send('您並非該刀主人喔!')
                else:
                  await message.channel.send('該刀不存在喔!')   
              else:
                await message.channel.send('[第幾刀]請使用阿拉伯數字!')
            else:
              await message.channel.send('!取消保留刀 格式錯誤，應為 !取消保留刀 [第幾刀]')
          else:
            pass #非指定頻道 不反應
          await CloseConnection(connection)

      elif tokens[0] == '!目前進度' or tokens[0] == '!目前进度' or tokens[0] == '!ns':
        if len(tokens) == 1:
          # check頻道，並找出所屬組別
          group_serial = 0
          connection = await OpenConnection()
          if connection:
            cursor = connection.cursor(prepared=True)
            sql = "SELECT now_week, now_boss, group_serial FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? order by group_serial limit 0, 1"
            data = (message.guild.id, message.channel.id)
            cursor.execute(sql, data) # 認證身分
            row = cursor.fetchone()
            cursor.close()
            if row:
              await message.channel.send('目前進度' + str(row[0]) + '週' + str(row[1]) + '王!')
            else:
              pass #非指定頻道 不反應

            CloseConnection(connection)
        else:
          await message.channel.send('!目前進度 格式錯誤，應為 !目前進度')
      
      elif tokens[0] == '!下面一位' or tokens[0] == '!下面一位' or tokens[0] == '!n':
        if len(tokens) == 1:
          # check頻道，並找出所屬組別
          group_serial = 0
          connection = await OpenConnection()
          if connection:
            cursor = connection.cursor(prepared=True)
            sql = "SELECT now_week, now_boss, boss_change, group_serial FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? order by group_serial limit 0, 1"
            data = (message.guild.id, message.channel.id)
            cursor.execute(sql, data) # 認證身分
            row = cursor.fetchone()
            cursor.close()
            if row:
              # CD檢查
              group_serial = row[3]
              boss_change = row[2]
              # UTC+0   UTC+8   =>   UTC+8
              if ( message.created_at + datetime.timedelta(hours = 8) - boss_change ).seconds >= 30: 
                now_week = row[0]
                now_boss = row[1]
                # 更新週目/boss
                if now_boss == 5:
                  now_week = now_week + 1
                  now_boss = 1
                else:
                  now_boss = now_boss + 1

                # 更新資料表
                cursor = connection.cursor(prepared=True)
                sql = "UPDATE princess_connect.group SET now_week=?, now_boss=?, boss_change=? WHERE server_id = ? and sign_channel_id = ?"
                data = (now_week, now_boss, (message.created_at + datetime.timedelta(hours = 8)).strftime("%Y-%m-%d %H:%M:%S"), message.guild.id, message.channel.id)
                cursor.execute(sql, data)
                cursor.close
                connection.commit()


                #tag成員
                knifes = ''
                cursor = connection.cursor(prepared=True)
                sql = "SELECT member_id FROM princess_connect.knifes WHERE server_id = ? and group_serial = ? and week=? and boss=?"
                data = (message.guild.id, group_serial, now_week ,now_boss)
                cursor.execute(sql, data)
                row = cursor.fetchone()
                while row:
                  mention = await get_mention(row[0])
                  knifes = knifes + mention  + ' '
                  row = cursor.fetchone()
                cursor.close()

                if knifes == '':
                  await message.channel.send('目前' + str(now_week) + '週' + str(now_boss) + '王沒人報刀喔，看在真步的面子上，快來報刀!')
                else:
                  await message.channel.send(knifes + str(now_week) + '週' + str(now_boss) + '王到囉!')


                # 更新刀表
                await Update(message.guild.id, group_serial) # 更新刀表
              else:
                await message.channel.send('目前CD中，上次使用時間:' + str(boss_change) + '。' )
            else:
              pass #非指定頻道 不反應

            await CloseConnection(connection)
        else:
          await message.channel.send('!下面一位 格式錯誤，應為 !下面一位')

      elif tokens[0] == '!出來打王' or tokens[0] == '!出来打王' or tokens[0] == '!hb':
        if len(tokens) == 1:
          # check頻道，並找出所屬組別
          group_serial = 0
          connection = await OpenConnection()
          if connection:
            cursor = connection.cursor(prepared=True)
            sql = "SELECT now_week, now_boss, group_serial FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? order by group_serial limit 0, 1"
            data = (message.guild.id, message.channel.id)
            cursor.execute(sql, data) # 認證身分
            row = cursor.fetchone()
            cursor.close()
            if row:
              now_week = row[0]
              now_boss = row[1]
              group_serial = row[2]
              knifes = ''
              cursor = connection.cursor(prepared=True)
              sql = "SELECT member_id FROM princess_connect.knifes WHERE server_id = ? and group_serial = ? and week=? and boss=?"
              data = (message.guild.id, group_serial, now_week ,now_boss)
              cursor.execute(sql, data)
              row = cursor.fetchone()
              while row:
                mention = await get_mention(row[0])
                knifes = knifes + mention  + ' '
                row = cursor.fetchone()
              cursor.close()

              if knifes == '':
                await message.channel.send('目前' + str(now_week) + '週' + str(now_boss) + '王沒人報刀喔，看在真步的面子上，快來報刀!')
              else:
                await message.channel.send(knifes + str(now_week) + '週' + str(now_boss) + '王到囉!')
            else:
              pass #非指定頻道 不反應
            await CloseConnection(connection)
        else:
          await message.channel.send('!出来打王 格式錯誤，應為 !出来打王')   

      # --------------------------------------------------------------------所有頻道，所有人皆可使用------------------------------------------------------------------------------------------------------          
    
      # 幫助訊息
      elif tokens[0] == '!幫助' or tokens[0] == '!帮助' or tokens[0] == '!h':
        msg = '\
**目前版本為為beta 0.8.4 版**\n\
\n\
指令支援繁體/簡體/英文，全形半形。\n\
此外，英文縮寫對照表於上方網頁文件中可以查詢。\n\
'
        embed_msg = Embed(title='說明(網頁好讀版請點我)', url='https://hackmd.io/@dkal/SysbG9clO', description=msg, color=0xB37084)
        embed_msg.set_author(name='咕嚕靈波（●′∀‵）ノ♡', url='https://discord.com/api/oauth2/authorize?client_id=806421470368104449&permissions=2048&scope=bot', icon_url='https://i.imgur.com/TtjU27j.jpg')
        embed_msg.add_field(name='第一步', value='請管理員先建立戰隊，並指派隊長。', inline=False)
        embed_msg.add_field(name='第二步', value='請各隊長先以指令設定好刀表、報刀、歷史紀錄，並設定好各頻道的權限，一般成員是以發言頻道做為判斷基準。', inline=False)
        embed_msg.add_field(name='第三步', value='開始使用囉!', inline=False)
        embed_msg.add_field(name='\u200b', value='\u200b', inline=False) # 空行
        msg = '\
請輸入以下指令來查看指令格式:\n\
　 !管理員專用指令\n\
或 !管理员专用指令\n\
或 !admcmd\n\
\n\
　 !戰隊隊長專用指令\n\
或 !战队队长专用指令\n\
或 !pricmd\n\
\n\
　 !控刀手專用指令\n\
或 !控刀手专用指令\n\
或 !concmd\n\
\n\
　 !一般指令\n\
或 !norcmd\n\
'
        embed_msg.add_field(name='指令格式', value=msg, inline=False)
        embed_msg.set_footer(text='當前版本可能會有些許BUG，歡迎反應或許願新功能!')
        await message.channel.send(embed=embed_msg)



      elif tokens[0] == '!管理員專用指令' or tokens[0] == '!管理员专用指令' or tokens[0] == '!admcmd':
        embed_msg = Embed(title='[管理員專用]', color=0xB87181)
        embed_msg.add_field(name='建立戰隊', value='建立戰隊，並將mention的人員全設為戰隊隊長。\n　!建立戰隊 [數字編號] [@隊長1 @隊長2 .....]\n　!建立战队 [數字編號] [@隊長1 @隊長2 .....]\n　!cg [數字編號] [@隊長1 @隊長2 .....]', inline=False)
        embed_msg.add_field(name='刪除戰隊', value='刪除指定戰隊資料，手起刀落，會砍得一乾二淨請謹慎使用。\n　!刪除戰隊 [數字編號]\n　!删除战队 [數字編號]\n　!dg [數字編號]', inline=False)
        embed_msg.add_field(name='戰隊隊長', value='更換指定戰隊隊長，採用內閣改組方式，會整組換掉，如有異動請全部重新mention一次。\n　!戰隊隊長 [數字編號] [@隊長1 @隊長2 .....]\n　!战队队长 [數字編號] [@隊長1 @隊長2 .....]\n　!gc [數字編號] [@隊長1 @隊長2 .....]', inline=False)
        embed_msg.add_field(name='戰隊列表', value='顯示所有戰隊資料。\n　!戰隊列表\n　!战队列表\n　!gl', inline=False)
        await message.channel.send(embed=embed_msg)



      elif tokens[0] == '!戰隊隊長專用指令' or tokens[0] == '!战队队长专用指令' or tokens[0] == '!pricmd':
        embed_msg = Embed(title='[戰隊隊長專用]', color=0xC5848B)
        embed_msg.add_field(name='控刀手身分組', value='把mention身分組設定為控刀手。\n　!控刀手身分組 [身分組]\n　!控刀手身分组 [身分組]\n　!cr [身分組]', inline=False)
        embed_msg.add_field(name='刀表在此', value='指定某一頻道作為顯示刀表的頻道，建議設定不可發言。\n　!刀表在此\n　!刀表在此\n　!tc', inline=False)
        embed_msg.add_field(name='報刀在此', value='指定某一頻道作為報刀的頻道，請用權限控制，僅有戰隊成員可發言。\n　!報刀在此\n　!报刀在此\n　!sc', inline=False)
        embed_msg.add_field(name='提前週目', value='設定可以提前幾個週目預約。\n　!提前週目 [幾週]\n　!提前周目 [幾週]\n　!wo [幾週]', inline=False)
        embed_msg.add_field(name='清除刀表', value='清除刀表，打掉重來。\n　!清除刀表\n　!清除刀表\n　!ct', inline=False)
        embed_msg.add_field(name='刀表樣式', value='切換刀表樣式。 0:Embed, 1:Text。\n　!刀表樣式 [代號]\n　!刀表样式 [代號]\n　!ts [代號]', inline=False)
        embed_msg.add_field(name='匯出刀表', value='傳送完整csv刀表到私人訊息。\n　!匯出刀表\n　!汇出刀表\n　!e', inline=False)
        await message.channel.send(embed=embed_msg)



      elif tokens[0] == '!控刀手專用指令' or tokens[0] == '!控刀手专用指令' or tokens[0] == '!concmd':
        embed_msg = Embed(title='[控刀手專用]', color=0xCFA6AC)
        embed_msg.add_field(name='移動', value='將該刀從[週目][boss][第幾刀]移動至[週目][boss]，簡單來說就是抽換刀序。\n　!移動 [週目] [boss] [哪一刀] [新週目] [新boss]\n　!移动 [週目] [boss] [哪一刀] [新週目] [新boss]\n　!m [週目] [boss] [哪一刀] [新週目] [新boss]', inline=False)
        embed_msg.add_field(name='刪除', value='刪除**刀表**中的某刀。請指明週目、boss與第幾刀。\n　!刪除 [週目] [boss] [第幾刀]\n　!删除 [週目] [boss] [第幾刀]\n　!fd [週目] [boss] [第幾刀]', inline=False)
        embed_msg.add_field(name='幫報', value='幫mention的人報刀至**刀表**。請指明週目、boss、備註與mention對方。\n　!幫報 [週目] [boss] [備註] [@成員]\n　!帮报 [週目] [boss] [備註] [@成員]\n　!hp [週目] [boss] [備註] [@成員]', inline=False)
        embed_msg.add_field(name='幫報保留刀', value='幫mention的人報刀至**保留區**。請指明boss、備註與mention對方。\n　!幫報保留刀 [boss] [備註] [@成員]\n　!帮报保留刀 [boss] [備註] [@成員]\n　!hkp [boss] [備註] [@成員]', inline=False)
        embed_msg.add_field(name='刪除保留刀', value='刪除**保留區**中的某刀。請指明第幾刀。\n　!刪除保留刀 [第幾刀]\n　!!删除保留刀 [第幾刀]\n　!fdkp [第幾刀]', inline=False)
        embed_msg.add_field(name='設定', value='調整當前boss進度，請指明週目與第幾boss。\n　!設定 [週目] [boss]\n　!设定 [週目] [boss]\n　!s [週目] [boss]', inline=False)        
        await message.channel.send(embed=embed_msg)



      elif tokens[0] == '!一般指令' or tokens[0] == '!norcmd':
        embed_msg = Embed(title='[一般指令]', color=0xD8B8BA)
        embed_msg.add_field(name='預約', value='報刀至**刀表**。請指明週目、boss與備註。\n　!預約 [週目] [幾王] [備註]\n　!预约 [週目] [幾王] [備註]\n　!p [週目] [幾王] [備註]', inline=False)
        embed_msg.add_field(name='取消預約', value='取消自己於**刀表**中的刀。請指明週目、boss與**刀表**中的第幾刀。\n　!取消預約 [週目] [幾王] [第幾刀]\n　!取消预约 [週目] [幾王] [第幾刀]\n　!cp [週目] [幾王] [第幾刀]', inline=False)
        embed_msg.add_field(name='報保留刀', value='報刀至**保留區**。請指明boss與備註。\n　!報保留刀 [幾王] [備註]\n　!报保留刀 [幾王] [備註]\n　!kp [幾王] [備註]', inline=False)
        embed_msg.add_field(name='使用保留刀', value='使用自己於**保留區**中的某刀。請指明**保留區**中的第幾刀，要出的週目與boss。\n　!使用保留刀 [第幾刀] [週目] [boss]\n　!使用保留刀 [第幾刀] [週目] [boss]\n　!ukp [第幾刀] [週目] [boss]', inline=False)
        embed_msg.add_field(name='取消保留刀', value='取消自己於**保留區**中的某刀。請指明boss與**保留區**中的第幾刀。\n　!取消保留刀 [第幾刀]\n　!取消保留刀 [第幾刀]\n　!ckp [第幾刀]', inline=False)
        embed_msg.add_field(name='目前進度', value='顯示目前王的進度，其實刀表最上方就是目前的進度。\n　!目前進度\n　!目前进度\n　!ns', inline=False)
        embed_msg.add_field(name='下面一位', value='進入下一王時使用，同時會tag下一王的成員，30秒僅能使用一次。\n　!下面一位\n　!下面一位\n　!n', inline=False)
        embed_msg.add_field(name='出來打王', value='tag當前王的出刀人員。\n　!出來打王\n　!出来打王\n　!hb', inline=False)
        await message.channel.send(embed=embed_msg)


  except Error as e:
    print("資料庫錯誤 ",e)
  except Exception as e:
    print("error ",e)
  
client.run(os.getenv('TOKEN'))