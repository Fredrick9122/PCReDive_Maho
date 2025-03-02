import datetime
from discord import Embed
from discord_slash.utils.manage_commands import create_option
import Discord_client
import Module.DB_control
import Module.Authentication
import Name_manager

@Discord_client.slash.subcommand( base="admin",
                                  name="group_list" ,
                                  description="顯示戰隊列表。",
                                )
async def group_list(ctx):
  if await Module.Authentication.IsAdmin(ctx ,'/group_list'):
    # 找出該伺服器戰隊
    connection = await Module.DB_control.OpenConnection(ctx)
    if connection:
      connection2 = await Module.DB_control.OpenConnection(ctx)
      if connection2:
        # 列出所有戰隊
        cursor = connection.cursor(prepared=True)
        sql = "SELECT server_id, group_serial, controller_role_id, table_channel_id, sign_channel_id FROM princess_connect.group WHERE server_id = ? order by group_serial"
        data = (ctx.guild.id, )
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
              channel = ctx.guild.get_channel(table_channel_id)
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
              channel = ctx.guild.get_channel(sign_channel_id)
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
              role = ctx.guild.get_role(controller_role_id)
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
            member_name = await Name_manager.get_nick_name(ctx, inner_row[0])
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
          await ctx.send('目前沒有戰隊!')
        else:
          await ctx.send(embed = embed_msg)

        await Module.DB_control.CloseConnection(connection2, ctx)

      await Module.DB_control.CloseConnection(connection, ctx)